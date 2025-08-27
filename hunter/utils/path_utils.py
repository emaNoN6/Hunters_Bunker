# ==========================================================
# Hunter's Command Console - Definitive Path Utility
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import os
import sys

# This variable will store the project root path once it's found.
_PROJECT_ROOT = None


def get_project_root():
	"""
	Finds and returns the absolute path to the project's root directory.
	It looks for a marker file (like 'config.ini') to identify the root.
	"""
	global _PROJECT_ROOT
	if _PROJECT_ROOT is not None:
		return _PROJECT_ROOT

	# Start from the location of this utility file and walk upwards
	current_path = os.path.dirname(os.path.abspath(__file__))

	# We'll use 'config.ini' as our reliable marker for the project root
	while not os.path.exists(os.path.join(current_path, 'config.ini')):
		parent_path = os.path.dirname(current_path)
		if parent_path == current_path:  # We've reached the filesystem root
			raise RuntimeError("Could not find the project root. Make sure 'config.ini' is in the root directory.")
		current_path = parent_path

	_PROJECT_ROOT = current_path
	return _PROJECT_ROOT


def setup_project_path():
	"""
	Ensures the project root is in the Python path for clean imports.
	"""
	project_root = get_project_root()
	if project_root not in sys.path:
		sys.path.insert(0, project_root)


# --- Run the setup automatically when this module is first imported ---
setup_project_path()
