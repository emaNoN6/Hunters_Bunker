# ===============================================
# Now accepts a standard set of arguments for consistency.

import requests


def hunt(target_info, credentials, log_queue, results_queue):
    """
    Performs a real search using the GNews API.
    'credentials' is a dictionary that holds all API keys.
    """

    # Helper function to send logs back to the main GUI
    def log(message):
        log_queue.put(f"[GNEWS AGENT]: {message}")

    target_location = target_info.get("target")
    keywords = target_info.get("keywords")
    api_key = credentials.get("gnews_api_key")

    log(f"Searching for '{keywords}' near '{target_location}'...")

    if not api_key or "YOUR_API_KEY_HERE" in api_key:
        log("ERROR: GNews API Key not configured in config.ini.")
        return

    keyword_string = f"({' OR '.join(keywords)})"
    query = f'"{target_location}" AND {keyword_string}'
    url = f"https://gnews.io/api/v4/search?q={query}&lang=en&country=us&max=10&apikey={api_key}"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])

        log(f"Search complete. Found {len(articles)} potential articles.")

        for article in articles:
            lead = {
                "source": f"GNews ({target_location})",
                "title": article["title"],
                "url": article["url"],
                "text": f"{article['title']}\n\n{article.get('description', '')}\n\n{article.get('content', '')}",
            }
            # Put the found lead into the results queue for the main app to process
            results_queue.put(lead)

    except requests.exceptions.RequestException as e:
        log(f"FATAL ERROR: Network or API error - {e}")
