# ==========================================================
# Hunter's Command Console - Definitive GNews.io Agent
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import requests
from datetime import datetime, timezone, timedelta


def hunt(log_queue, source, credentials):
	"""
	Hunts GNews.io for new articles since the last check.
	"""
	query = source.get('target')
	last_checked = source.get('last_checked_date')
	source_name = source.get('source_name')

	log_queue.put(f"[{source_name}]: Waking up. Hunting for '{query}'...")

	if not credentials or not credentials.get('api_key'):
		log_queue.put(f"[{source_name} ERROR]: GNews.io API key not provided.")
		return [], None

	# --- Prepare the API Request ---
	# GNews API URL
	url = "https://gnews.io/api/v4/search"

	# Set parameters for the API call
	params = {
		'q':       query,
		'token':   credentials['api_key'],
		'lang':    'en',
		'country': 'us',
		'max':     10,  # Limit to 10 articles per run to be safe
		'sortby':  'publishedAt'
	}

	# If we have a last_checked_date, tell the API to only get articles
	# published since then. We subtract an hour as a safety buffer.
	if last_checked:
		start_time = last_checked - timedelta(hours=1)
		# Format the date into the ISO 8601 format the API requires (e.g., 2025-08-17T12:00:00Z)
		params['from'] = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
		log_queue.put(f"[{source_name}]: Searching for articles published after {params['from']}")

	# --- Execute the Hunt ---
	leads = []
	try:
		response = requests.get(url, params=params)
		response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
		articles = response.json().get('articles', [])

		for article in articles:
			# The API gives a date string in UTC (Zulu time).
			# We parse it into a timezone-aware datetime object.
			publication_date = datetime.strptime(article['publishedAt'], '%Y-%m-%dT%H:%M:%SZ').replace(
				tzinfo=timezone.utc)

			lead_data = {
				"title":            article['title'],
				"url":              article['url'],
				"text":             article.get('content', ''),  # Use .get() for safety
				"html":             None,  # News APIs rarely provide full HTML
				"publication_date": publication_date,
				"source_name":      source_name
			}
			leads.append(lead_data)

		# We don't have a "newest_id" for news APIs, so we return None.
		# The dispatcher will simply update the last_checked_date to now().
		log_queue.put(f"[{source_name}]: Hunt successful. Returned {len(leads)} new leads.")
		return leads, None

	except Exception as e:
		log_queue.put(f"[{source_name} ERROR]: An error occurred during the hunt: {e}")
		return [], None
