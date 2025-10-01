# ==========================================================
# Hunter's Command Console - GNews.io Foreman
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

from datetime import datetime, timezone
from search_agents import gnews_io_agent
import logging
logger = logging.getLogger(__name__)

def run_hunt(source, credentials):
	"""
	Manages a hunt on a GNews.io source. It deploys an agent, receives the
	raw intel, and translates it into Standardized Lead Reports.
	"""
	try:
		# 1. Deploy the agent to get the raw intel
		raw_articles, newest_id_found = gnews_io_agent.hunt(source, credentials)
	except Exception as e:
		logger.error(f"[GNEWS_FOREMAN ERROR]: The hunt conducted by the agent failed critically: {e}")
		return None, None

	if raw_articles is None:
		return None, None

	# 2. Translate the raw intel into standardized reports
	standardized_reports = []
	for article in raw_articles:
		report = _translate_article(article, source['id'], source['source_name'])
		if report:
			standardized_reports.append(report)

	# GNews doesn't use bookmarks, so newest_id_found will be None
	return standardized_reports, newest_id_found


def _translate_article(raw_article, source_id, source_name):
	"""
	Translates a single raw article dictionary into a Standardized Lead Report.
	"""
	try:
		# The API gives a date string in UTC (Zulu time).
		# We parse it into a timezone-aware datetime object.
		publication_date = datetime.strptime(raw_article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(
			tzinfo=timezone.utc)

		standardized_report = {
			"title":            raw_article['title'],
			"url":              raw_article['url'],
			"publication_date": publication_date,
			"text_content":     raw_article.get('content', ''),
			"html_content":     None,  # News APIs rarely provide full HTML
			"source_id":        source_id,
			"source_name":      source_name,
			"triage_metadata":  {},  # No extra metadata from this source for now
		}
		return standardized_report
	except Exception as e:
		logger.error(f"[GNEWS_FOREMAN ERROR]: Failed to translate article '{raw_article.get('title', 'N/A')}': {e}")
		return None
