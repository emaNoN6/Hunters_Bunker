# ==========================================================
# Hunter's Command Console - Keyword Populator (from File)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import os
import sys

# --- NEW Centralized Pathing ---
# Using the new project utility to handle path setup.
# This makes the script runnable from any location.
from hunter.path_utils import project_path

# --- End Pathing ---

from hunter import db_admin

# --- Configuration ---
# The path to your curated keyword file, relative to the project root.
KEYWORD_FILE_PATH = "data/curated_keywords.csv"

# The themes in the order they appear in the file.
THEMES = ["GHOST", "DEMON", "CRYPTOZOOLOGY"]


def populate_library_from_file():
	"""
	Reads a curated, comma-separated file and populates the keyword library.
	"""
	print(f"Populating keyword library from '{KEYWORD_FILE_PATH}'...")

	full_path = project_path(KEYWORD_FILE_PATH, start_path=__file__)

	try:
		with open(full_path, 'r') as f:
			lines = f.readlines()
	except FileNotFoundError:
		print(f"[ERROR]: Keyword file not found at '{full_path}'. Aborting.")
		return

	all_keywords_to_add = []
	theme_index = 0

	for line in lines:
		line = line.strip()
		if not line:  # Skip blank lines
			continue

		if theme_index < len(THEMES):
			theme = THEMES[theme_index]
			keywords = [k.strip().lower() for k in line.split(',')]

			print(f" -> Found {len(keywords)} keywords for theme: {theme}")

			for keyword in keywords:
				if keyword:  # Avoid empty strings
					all_keywords_to_add.append((keyword, theme))

			theme_index += 1
		else:
			print(f"[WARNING]: Found more data lines than expected themes. Ignoring extra line: '{line[:50]}...'")

	if all_keywords_to_add:
		print(f"Adding a total of {len(all_keywords_to_add)} keywords to the database...")
		db_admin.add_keywords(all_keywords_to_add)

	print("Keyword library population complete.")


if __name__ == "__main__":
	populate_library_from_file()
