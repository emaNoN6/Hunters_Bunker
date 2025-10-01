# ==========================================================
# Hunter's Command Console - Test Data Foreman (Corrected)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import random
import logging
from datetime import datetime, timezone, timedelta
from search_agents import test_data_agent

# Get a logger for this module
logger = logging.getLogger("Test Foreman")


def run_hunt(source, credentials=None):
	"""
	Manages a hunt using the test_data_agent and translates the results.
	"""
	try:
		# --- THIS IS THE FIX ---
		# The agent no longer needs the log_queue, so we don't pass it.
		raw_leads, newest_id_found = test_data_agent.hunt(source, credentials)
	# --- END FIX ---
	except Exception as e:
		logger.error(f"The hunt conducted by the test_data_agent failed critically.", exc_info=True)
		return None, None

	if raw_leads is None:
		return None, None

	# Translate the raw intel into standardized reports
	standardized_reports = []
	for lead in raw_leads:
		report = _translate_lead(lead, source['id'], source['source_name'])
		if report:
			standardized_reports.append(report)

	return standardized_reports, None


def _translate_lead(raw_lead, source_id, source_name):
	"""
	Translates a single raw lead dictionary into a Standardized Lead Report.
	"""
	try:
		if 'publication_date' in raw_lead and raw_lead['publication_date']:
			pub_date_raw = raw_lead['publication_date']
			if isinstance(pub_date_raw, str):
				try:
					dt = datetime.fromisoformat(pub_date_raw)
					publication_date = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
				except ValueError:
					logger.warning(f"Could not parse date string '{pub_date_raw}'. Assigning placeholder.")
					publication_date = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
			else:
				publication_date = pub_date_raw.replace(
					tzinfo=timezone.utc) if pub_date_raw.tzinfo is None else pub_date_raw
		else:
			logger.warning(f"Lead '{raw_lead.get('title')}' is missing a date. Assigning placeholder.")
			publication_date = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

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
		logger.error(f"Failed to translate lead '{raw_lead.get('title', 'N/A')}'.", exc_info=True)
		return None
