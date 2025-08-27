# ==========================================================
# Hunter's Command Console - Test Data Foreman
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import random
from datetime import datetime, timezone, timedelta
from search_agents import test_data_agent


def run_hunt(log_queue, source, credentials=None):
	"""
	Manages a hunt using the test_data_agent and translates the results.
	"""
	try:
		# 1. Deploy the agent to get the raw intel (list of dicts)
		raw_leads, newest_id_found = test_data_agent.hunt(log_queue, source, credentials)
	except Exception as e:
		log_queue.put(f"[TEST_DATA_FOREMAN ERROR]: The hunt failed critically: {e}")
		return None, None

	if raw_leads is None:
		return None, None

	# 2. Translate the raw intel into standardized reports
	standardized_reports = []
	for lead in raw_leads:
		report = _translate_lead(log_queue, lead, source['id'], source['source_name'])
		if report:
			standardized_reports.append(report)

	# Test data doesn't use bookmarks
	return standardized_reports, None


def _translate_lead(log_queue, raw_lead, source_id, source_name):
	"""
	Translates a single raw lead dictionary into a Standardized Lead Report.
	This includes robust date handling for test data.
	"""
	try:
		# --- Date Handling ---
		# Ensure every lead has a valid, timezone-aware publication_date
		if 'publication_date' in raw_lead and raw_lead['publication_date']:
			pub_date_raw = raw_lead['publication_date']
			if isinstance(pub_date_raw, str):
				try:
					dt = datetime.fromisoformat(pub_date_raw)
					publication_date = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
				except ValueError:
					log_queue.put(
						f"[{source_name} WARNING]: Could not parse date string '{pub_date_raw}'. Assigning random date.")
					publication_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))
			else:  # Assume it's already a datetime object
				publication_date = pub_date_raw.replace(
					tzinfo=timezone.utc) if pub_date_raw.tzinfo is None else pub_date_raw
		else:
			# If no date is provided, create a plausible fake one for testing.
			log_queue.put(
				f"[{source_name} WARNING]: Lead '{raw_lead.get('title')}' is missing a date. Assigning random date.")
			publication_date = datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30))

		standardized_report = {
			"title":            raw_lead.get('title', 'Untitled Test Lead'),
			"url":              raw_lead.get('url', ''),
			"publication_date": publication_date,
			"text_content":     raw_lead.get('text', ''),
			"html_content":     raw_lead.get('html'),
			"source_id":        source_id,
			"source_name":      source_name,
			"triage_metadata":  raw_lead.get('triage_metadata', {}),
		}
		return standardized_report

	except Exception as e:
		print(f"[TEST_DATA_FOREMAN ERROR]: Failed to translate lead '{raw_lead.get('title', 'N/A')}': {e}")
		return None
