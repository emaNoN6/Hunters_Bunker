# ==========================================================
# Hunter's Command Console - GNews.io Agent (v3 - Simplified)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import requests
from datetime import datetime, timezone, timedelta
import logging
logger = logging.getLogger("GnewsIO Agent")

def hunt(source, credentials):
	"""
	Hunts GNews.io for new articles.
	This agent is a "dumb scout". Its only job is to fetch the raw data
	and return it. The foreman is responsible for all translation.
	"""
	query = source.get('target')
	# The db_manager provides last_checked as a datetime object
	last_checked = source.get('last_checked')
	source_name = source.get('name')

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

	# Use last_checked as a bookmark, with a 1-hour safety buffer
	# to account for any API delays or clock skew.
	if last_checked:
		start_time = last_checked - timedelta(hours=1)
		# GNews requires ISO 8601 format with 'Z' for UTC.
		params['from'] = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
		logger.info(f"[{source_name}]: Searching for articles published after {params['from']}")

	# --- Execute the Hunt ---
	try:
		response = requests.get(url, params=params)
		# Will raise an HTTPError for bad responses (4xx or 5xx)
		response.raise_for_status()
		articles = response.json().get('articles', [])

		# The agent's job is complete. It returns the raw, unprocessed intel.
		# The foreman will handle all translation and data cleaning.
		logger.info(f"[{source_name}]: Hunt successful. Returned {len(articles)} raw articles.")
		return articles, None

	except requests.exceptions.RequestException as e:
		logger.error(f"[{source_name} ERROR]: A network error occurred during the hunt: {e}")
		return [], None
	except Exception as e:
		logger.error(f"[{source_name} ERROR]: An unexpected error occurred during the hunt: {e}")
		return [], None
