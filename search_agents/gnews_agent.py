#  ==========================================================
#  Hunter's Command Console
#  #
#  File: gnews_agent.py
#  Last Modified: 7/27/25, 2:57 PM
#  Copyright (c) 2025, M. Stilson & Codex
#  #
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the MIT License.
#  #
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  LICENSE file for more details.
#  ==========================================================

# search_agents/gnews_agent.py

from gnews import GNews
from hunter import db_manager


def hunt(log_queue, source):
    """
    Searches for news articles using the GNews library based on keywords.
    """
    keyword = source.get("target")
    source_id = source.get("id")
    source_name = source.get("source_name")

    log_queue.put(f"[{source_name}]: Waking up. Searching for '{keyword}'...")

    results = []
    try:
        google_news = GNews(language="en", country="US", period="7d")
        news = google_news.get_news(keyword)

        log_queue.put(f"[{source_name}]: Found {len(news)} potential leads.")

        for item in news:
            # Check if we've already processed this article
            if db_manager.check_acquisition_log(item["url"]):
                continue

            lead_data = {
                "title": item["title"],
                "url": item["url"],
                "source": source_name,
                "text": item["description"],
                "html": f"<h1>{item['title']}</h1><p>{item['description']}</p><p><a href='{item['url']}' target='_blank'>Read More</a></p>",
            }
            results.append(lead_data)
            # Log this item so we don't process it again
            db_manager.log_acquisition(
                item["url"], source_id, item["title"], "PROCESSED"
            )

        return results

    except Exception as e:
        log_queue.put(f"[{source_name} ERROR]: {e}")
        # Here we would update the source's failure count in a real scenario
        return []
