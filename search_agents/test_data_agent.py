# ==========================================================
# Hunter's Command Console - Definitive Test Data Agent (Corrected)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import json
import os
import logging
from datetime import datetime, timezone

# --- Centralized Pathing ---
import hunter.utils.path_utils
from hunter.utils.path_utils import get_project_root

# --- End Pathing ---

# Get a logger for this module
logger = logging.getLogger("Test Agent")


def hunt(source, credentials=None):
	"""
	Loads leads from a local JSON file for testing purposes.
	Relies on a consistent publication_date within the JSON for de-duplication.
	"""
	file_path = source.get('target')
	source_name = source.get('source_name')

	logger.info(f"Waking up. Loading test data from '{file_path}'...")

	full_path = os.path.join(get_project_root(), 'data', file_path)

	try:
		with open(full_path, 'r') as f:
			test_leads = json.load(f)
	except FileNotFoundError:
		logger.error(f"Test data file not found at '{full_path}'.")
		return [], None
	except Exception as e:
		logger.error(f"Failed to load or parse test data: {e}", exc_info=True)
		return [], None

	processed_leads = []

	for lead in test_leads:
		# --- THIS IS THE FIX ---
		# The agent now relies on the JSON file to provide a consistent date.
		# It will only create a placeholder if the date is missing entirely.
		if 'publication_date' not in lead or not lead['publication_date']:
			logger.warning(f"Test lead '{lead.get('title')}' is missing a publication_date. Assigning a placeholder.")
			# Use a truly static placeholder for consistency
			lead['publication_date'] = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
		# --- END FIX ---

		if 'source_name' not in lead:
			lead['source_name'] = source_name

		processed_leads.append(lead)

	logger.info(f"Hunt successful. Loaded {len(processed_leads)} test leads.")

	return processed_leads, None
