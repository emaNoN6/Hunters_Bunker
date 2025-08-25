# ==========================================================
# Hunter's Command Console - Definitive Keyword Populator
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import os
import sys
import time

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_admin, config_manager
from hunter import llm_helper


def populate_library():
	"""
	Uses the Gemini LLM to generate and populate the keyword library.
	"""
	print("Populating keyword library using Gemini API...")

#	api_key = config_manager.get_gemini_credentials().get('api_key')
	api_key = "AIzaSyAdtu0jH7at-DV9LjdQlmpfrvVXUCv-S7o"
	if not api_key:
		print("Gemini API key not found in config.ini. Aborting.")
		return

	themes_to_generate = {
		"GHOST":         "Generate a comprehensive, comma-separated list of keywords, synonyms, and related terms for ghost sightings, hauntings, and apparitions.",
		"DEMON":         "Generate a comprehensive, comma-separated list of keywords, synonyms, and related terms for demonic possession, entities, and exorcisms.",
		"CRYPTOZOOLOGY": "Generate a comprehensive, comma-separated list of keywords, synonyms, and related terms for cryptids, mythical creatures, and unknown animals like Bigfoot or Mothman."
	}

	all_keywords_to_add = []

	for theme, prompt in themes_to_generate.items():
		print(f" -> Generating keywords for theme: {theme}")

		keyword_string = llm_helper.generate_text(prompt, api_key)

		if not keyword_string:
			print(f" -> Failed to generate keywords for {theme}. Skipping.")
			continue

		keywords = [k.strip().lower() for k in keyword_string.split(',')]

		for keyword in keywords:
			if keyword:
				all_keywords_to_add.append((keyword, theme))

		# Be polite to the API, wait a second between calls
		time.sleep(1)

	if all_keywords_to_add:
		print(f"Adding a total of {len(all_keywords_to_add)} keywords to the database...")
		db_admin.add_keywords(all_keywords_to_add)

	print("Keyword library population complete.")


if __name__ == "__main__":
	populate_library()
