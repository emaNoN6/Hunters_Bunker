# ==========================================================
# Hunter's Command Console - Definitive GNews.io Agent (v2)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import requests
from datetime import datetime, timezone, timedelta
import logging
logger = logging.getLogger("GnewsIO Agent")

def hunt(source, credentials):
	"""
	Hunts GNews.io for new articles since the last check.
	"""
	query = source.get('target')
	last_checked = source.get('last_checked_date')
	source_name = source.get('source_name')

	logger.info(f"[{source_name}]: Waking up. Hunting for '{query}'...")

	if not credentials or not credentials.get('api_key'):
		logger.error(f"[{source_name} ERROR]: GNews.io API key not provided.")
		return [], None

	# --- Prepare the API Request ---
	url = "https://gnews.io/api/v4/search"
	params = {
		'q':       query,
		'token':   credentials['api_key'],
		'lang':    'en',
		'country': 'us',
		'max':     10,
		'sortby':  'publishedAt'
	}

	# Use last_checked_date as a bookmark, with a 1-hour safety buffer
	if last_checked:
		start_time = last_checked - timedelta(hours=1)
		params['from'] = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
		logger.info(f"[{source_name}]: Searching for articles published after {params['from']}")

	# --- Execute the Hunt ---
	leads = []
	try:
		response = requests.get(url, params=params)
		response.raise_for_status()
		articles = response.json().get('articles', [])

		for article in articles:
			publication_date = datetime.strptime(article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(
				tzinfo=timezone.utc)

			lead_data = {
				"title":            article['title'],
				"url":              article['url'],
				"text":             article.get('content', ''),
				"html":             None,
				"publication_date": publication_date,
				"source_name":      source_name
			}
			leads.append(lead_data)

		# News APIs don't use bookmarks, so we return None for the newest_id
		logger.info(f"[{source_name}]: Hunt successful. Returned {len(leads)} new leads.")
		return leads, None

	except Exception as e:
		logger.error(f"[{source_name} ERROR]: An error occurred during the hunt: {e}")
		return [], None
