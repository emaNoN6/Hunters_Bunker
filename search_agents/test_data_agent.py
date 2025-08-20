# ==========================================================
# Hunter's Command Console - Definitive Test Data Agent
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import json
import os
import random
from datetime import datetime, timezone, timedelta


def hunt(log_queue, source, credentials=None):
	"""
	Loads leads from a local JSON file for testing purposes.
	Conforms to the new agent contract.
	"""
	file_path = source.get('target')
	source_name = source.get('source_name')

	log_queue.put(f"[{source_name}]: Waking up. Loading test data from '{file_path}'...")

	# Construct the full path to the data file, assuming it's in a 'data' directory
	# relative to the project root.
	try:
		project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
		full_path = os.path.join(project_root, 'data', file_path)

		with open(full_path, 'r') as f:
			test_leads = json.load(f)
	except FileNotFoundError:
		log_queue.put(f"[{source_name} ERROR]: Test data file not found at '{full_path}'.")
		return [], None
	except Exception as e:
		log_queue.put(f"[{source_name} ERROR]: Failed to load or parse test data: {e}")
		return [], None

	processed_leads = []
	for lead in test_leads:
		# --- Date Handling ---
		# Ensure every lead has a valid, timezone-aware publication_date
		if 'publication_date' in lead and lead['publication_date']:
			# If the date is a string, parse it. Assumes ISO 8601 format.
			if isinstance(lead['publication_date'], str):
				try:
					# Attempt to parse with timezone info first
					dt = datetime.fromisoformat(lead['publication_date'])
					# If no timezone info, assume UTC
					if dt.tzinfo is None:
						lead['publication_date'] = dt.replace(tzinfo=timezone.utc)
					else:
						lead['publication_date'] = dt
				except ValueError:
					log_queue.put(
						f"[{source_name} WARNING]: Could not parse date string '{lead['publication_date']}'. Assigning random date.")
					lead['publication_date'] = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
			# If it's already a datetime object, ensure it's timezone-aware
			elif isinstance(lead['publication_date'], datetime) and lead['publication_date'].tzinfo is None:
				lead['publication_date'] = lead['publication_date'].replace(tzinfo=timezone.utc)
		else:
			# If no date is provided, create a plausible fake one for testing.
			log_queue.put(
				f"[{source_name} WARNING]: Lead '{lead.get('title')}' is missing a date. Assigning random date.")
			lead['publication_date'] = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))

		# Ensure source_name is present
		if 'source_name' not in lead:
			lead['source_name'] = source_name

		processed_leads.append(lead)

	log_queue.put(f"[{source_name}]: Hunt successful. Loaded {len(processed_leads)} test leads.")

	# This agent doesn't use bookmarks, so it always returns None for the newest_id
	return processed_leads, None
