# search_agents/gnews_io_agent.py

import requests
from hunter import http_utils  # Use relative import

API_ENDPOINT = "https://gnews.io/api/v4/search"


def hunt(log_queue, source, gnews_creds):
	"""
    Searches for news articles using the gnews.io API.
    Credentials are now passed in directly by the dispatcher.
    """
	keyword = source.get('target')
	source_name = source.get('source_name')

	log_queue.put(f"[{source_name}]: Waking up. Querying gnews.io for '{keyword}'...")

	if not gnews_creds or not gnews_creds.get('api_key'):
		log_queue.put(f"[{source_name} ERROR]: GNews.io API key was not provided by dispatcher.")
		return []

	params = {
		'q':       keyword,
		'lang':    'en',
		'country': 'us',
		'max':     10,
		'apikey':  gnews_creds['api_key']
	}

	results = []
	try:
		headers = http_utils.get_stealth_headers(API_ENDPOINT)
		response = requests.get(API_ENDPOINT, params=params, headers=headers)
		response.raise_for_status()
		data = response.json()
		articles = data.get('articles', [])

		log_queue.put(f"[{source_name}]: Found {len(articles)} potential leads.")

		for item in articles:
			lead_data = {
				"title":            item['title'],
				"url":              item['url'],
				"source":           source_name,
				"publication_date": item['publishedAt'],
				"text":             item.get('description', ''),
				"html":             f"<h1>{item['title']}</h1><p>{item.get('description', '')}</p><p><b>Source:</b> {item['source']['name']}</p><p><a href='{item['url']}' target='_blank'>Read More</a></p>"
			}
			results.append(lead_data)

		return results

	except Exception as e:
		log_queue.put(f"[{source_name} ERROR]: {e}")
		return []
