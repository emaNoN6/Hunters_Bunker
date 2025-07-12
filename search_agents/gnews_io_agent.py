# search_agents/gnews_io_agent.py

import requests
import db_manager
import config_manager
import time

# The base URL for the gnews.io API
API_ENDPOINT = "https://gnews.io/api/v4/search"


def hunt(log_queue, source):
    """
    Searches for news articles using the gnews.io API.
    """
    keyword = source.get("target")
    source_id = source.get("id")
    source_name = source.get("source_name")

    log_queue.put(f"[{source_name}]: Waking up. Querying gnews.io for '{keyword}'...")

    creds = config_manager.get_gnews_io_credentials()
    if not creds or not creds.get("api_key"):
        log_queue.put(
            f"[{source_name} ERROR]: GNews.io API key not found in config.ini"
        )
        return []

    params = {
        "q": keyword,
        "lang": "en",
        "country": "us",
        "max": 10,
        "apikey": creds["api_key"],
    }

    results = []
    try:
        response = requests.get(API_ENDPOINT, params=params)
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])

        log_queue.put(f"[{source_name}]: Found {len(articles)} potential leads.")

        for item in articles:
            # Check if we've already processed this article
            if db_manager.check_acquisition_log(item["url"]):
                continue

            lead_data = {
                "title": item["title"],
                "url": item["url"],
                "source": source_name,
                "text": item.get("description", ""),
                "html": f"<h1>{item['title']}</h1><p>{item.get('description', '')}</p><p><b>Source:</b> {item['source']['name']}</p><p><a href='{item['url']}' target='_blank'>Read More</a></p>",
            }
            results.append(lead_data)

        return results

    except Exception as e:
        log_queue.put(f"[{source_name} ERROR]: {e}")
        # Here we would update the source's failure count in a real scenario
        return []
