#!/usr/bin/env python3
# ==========================================================
# Hunter's Command Console - Morphology Cache Populator
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import argparse
import sys
import requests
from pyinflect import getAllInflections
# --- Centralized Pathing ---
from hunter.utils.path_utils import setup_project_path

setup_project_path()
# --- End Pathing ---

from hunter import config_manager, db_admin, db_manager

# Track state
processed_words = set()
api_calls_made = 0
MAX_CALLS_PER_RUN = 250  # Safety limit - stay well under 2500
max_calls = MAX_CALLS_PER_RUN


def fetch_word_from_api(word, api_key, api_host):
	"""Fetch word data from WordsAPI"""
	url = f"https://{api_host}/words/{word}"
	headers = {
		"x-rapidapi-key":  api_key,
		"x-rapidapi-host": api_host
	}

	try:
		response = requests.get(url, headers=headers, timeout=10)

		# Log the API call with rate limit info
		db_admin.log_api_call('wordsapi', f'/words/{word}', word, response.status_code, response.headers)

		if response.status_code == 200:
			return response.json()
		elif response.status_code == 404:
			print(f"  ⚠️  Word '{word}' not found in API")
			return None
		else:
			print(f"  ⚠️  API error for '{word}': {response.status_code}")
			return None
	except requests.exceptions.RequestException as e:
		print(f"  ❌ Network error fetching '{word}': {e}")
		return None


def process_word(word, depth, max_depth, api_key, api_host, dry_run=False):
	"""Process a single word and optionally recurse through synonyms"""
	global api_calls_made, processed_words

	# Skip if already processed in this run
	if word in processed_words:
		return

	# Check if already cached in DB
	cached = db_manager.get_search_term(word)
	if cached:
		print(f"  ✓ '{word}' already cached, skipping")
		processed_words.add(word)
		return

	# Safety check - don't exceed our per-run limit
	if api_calls_made >= max_calls:
		print(f"\n⚠️  Reached max API calls per run ({max_calls}), stopping")
		return

	indent = "  " * depth
	print(f"{indent}→ Fetching '{word}' from API (depth {depth})...")

	if dry_run:
		print(f"{indent}  [DRY RUN] Would fetch and store '{word}'")
		processed_words.add(word)
		return

	# Fetch from API
	response = fetch_word_from_api(word, api_key, api_host)
	api_calls_made += 1

	if not response:
		# Store a minimal entry so we don't try to fetch it again
		# Inflect can still try to conjugate it in Pass 2
		minimal_response = {
			"word":    word,
			"results": [],
			"note":    "not_found_in_api"
		}
		if not dry_run:
			db_admin.store_search_term(word, minimal_response)
			print(f"{indent}  → Stored as 'not found' (won't retry)")
		processed_words.add(word)
		return

	# Store the base term with a full JSON response
	if not db_admin.store_search_term(word, response):
		print(f"{indent}  ❌ Failed to store term")
		processed_words.add(word)
		return

	print(f"{indent}  ✓ Stored term '{word}'")

	# Extract and store derivations from all senses
	derivations = set()
	for result in response.get('results', []):
		for deriv in result.get('derivation', []):
			if deriv:  # Skip empty strings
				derivations.add(deriv.lower().strip())

	for deriv in derivations:
		if deriv != word:  # Don't store word as its own derivation
			db_admin.store_derivation(word, deriv, source='wordsapi')

	if derivations:
		print(f"{indent}  ✓ Stored {len(derivations)} derivations")

	# Extract and store synonyms with their context
	synonyms = set()
	for idx, result in enumerate(response.get('results', [])):
		definition = result.get('definition', '')
		for syn in result.get('synonyms', []):
			if syn:  # Skip empty strings
				syn_clean = syn.lower().strip()
				synonyms.add(syn_clean)
				db_admin.store_synonym(word, syn_clean, idx, definition[:100])

	if synonyms:
		print(f"{indent}  ✓ Stored {len(synonyms)} synonyms")

	processed_words.add(word)

	# Recurse through synonyms if depth allows
	if depth < max_depth and synonyms:
		print(f"{indent}  → Recursing into {len(synonyms)} synonyms...")
		for syn in list(synonyms):  # Convert to list to avoid modification during iteration
			if api_calls_made >= max_calls:
				print(f"{indent}  ⚠️  Hit API call limit during recursion")
				break
			process_word(syn, depth + 1, max_depth, api_key, api_host, dry_run)


def generate_conjugations(dry_run=False):
	"""Second pass: generate verb/noun conjugations using inflect"""
	print("\n=== PASS 2: Generating Conjugations ===")

	# p = inflect.engine()
	terms = db_manager.get_all_search_terms()

	if not terms:
		print("No terms found in database")
		return

	print(f"Processing {len(terms)} cached terms...")

	conjugations_added = 0

	for term_data in terms:
		base_term = term_data['base_term']
		api_response = term_data['api_response']

		if dry_run:
			print(f"  [DRY RUN] Would add inflections for '{base_term}'")
			continue

		all_terms = set()
		inflections = getAllInflections(base_term)
		if inflections:
			for tag, forms in inflections.items():
				all_terms.update(forms)
		all_terms.discard(base_term)

		for term in all_terms:
			db_admin.store_derivation(base_term, term, source='pyinflect')
			conjugations_added += 1

	print(f"✓ Added {conjugations_added} conjugations via inflect")


def main():
	parser = argparse.ArgumentParser(
			description='Populate morphology cache from WordsAPI',
			formatter_class=argparse.RawDescriptionHelpFormatter,
			epilog="""
Examples:
  python tools/populate_morphology.py demon
  python tools/populate_morphology.py demon --depth 2
  python tools/populate_morphology.py --file paranormal_terms.txt
  python tools/populate_morphology.py --conjugate-only
  python tools/populate_morphology.py demon --dry-run
  python tools/populate_morphology.py demon --max-calls 100
        """
	)

	parser.add_argument('word', nargs='?', help='Single word to process')
	parser.add_argument('--file', help='File containing words (one per line)')
	parser.add_argument('--depth', type=int, default=1,
	                    help='Synonym recursion depth (default: 1, max: 2)')
	parser.add_argument('--dry-run', action='store_true',
	                    help='Show what would be done without making changes')
	parser.add_argument('--conjugate-only', action='store_true',
	                    help='Only run conjugation pass on existing data')
	parser.add_argument('--max-calls', type=int, default=MAX_CALLS_PER_RUN,
	                    help=f'Maximum number of API calls per run 0 for unlimited (default: {MAX_CALLS_PER_RUN})')

	args = parser.parse_args()

	# Validate arguments
	if not args.conjugate_only and not args.word and not args.file:
		parser.error("Must provide either a word, --file, or --conjugate-only")

	if args.depth > 2:
		print("⚠️  Maximum depth is 2, using 2")
		args.depth = 2

	print("=== Morphology Cache Populator ===\n")

	# Get API credentials
	if not args.conjugate_only:
		creds = config_manager.get_wordsapi_credentials()
		if not creds:
			print("❌ WordsAPI credentials not found in config.ini")
			sys.exit(1)

		api_key = creds.get('api_key')
		api_host = creds.get('api_host')

		if not api_key or not api_host:
			print("❌ Incomplete WordsAPI credentials in config.ini")
			sys.exit(1)

		# Check API safety before starting
		is_safe, remaining, message = db_manager.check_api_safety(min_remaining=50)
		print(f"API Status: {message}")

		if not is_safe and not args.dry_run:
			print("❌ Not safe to proceed with API calls")
			sys.exit(1)

		print()

	global max_calls
	max_calls = MAX_CALLS_PER_RUN
	if args.max_calls == 0 or args.max_calls > 2450:
		max_calls = remaining - 50
	else:
		max_calls = args.max_calls
	print(f"Max API calls per run: {max_calls}")

	# Handle conjugate-only mode
	if args.conjugate_only:
		generate_conjugations(args.dry_run)
		print("\n✓ Conjugation pass complete")
		return

	# Build word list
	print("=== PASS 1: Fetching from WordsAPI ===")
	words = []

	if args.word:
		words.append(args.word.lower().strip())
	elif args.file:
		try:
			with open(args.file, 'r') as f:
				words = [line.strip().lower() for line in f if line.strip() and not line.startswith('#')]
			print(f"Loaded {len(words)} words from {args.file}")
		except FileNotFoundError:
			print(f"❌ File not found: {args.file}")
			sys.exit(1)

	if not words:
		print("❌ No words to process")
		sys.exit(1)

	print(f"Processing {len(words)} word(s) with synonym depth {args.depth}...\n")

	# Process each word
	for word in words:
		if not word:
			continue
		process_word(word, depth=0, max_depth=args.depth,
		             api_key=api_key, api_host=api_host, dry_run=args.dry_run)

	# Pass 2: Conjugations (skip if dry run or if we didn't fetch anything)
	if not args.dry_run and processed_words:
		generate_conjugations()

	# Print summary stats
	print("\n=== Summary ===")
	print(f"API calls made: {api_calls_made}")
	print(f"Unique words processed: {len(processed_words)}")

	if not args.dry_run:
		all_terms = db_manager.get_all_search_terms()
		print(f"Total terms in cache: {len(all_terms)}")

	print("\n✓ Complete")


if __name__ == '__main__':
	main()
