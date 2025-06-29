# FILE 3: search_agents/reddit_agent.py (WITH DEBUG LOGGING)
# ===========================================================
# We'll log the credentials right when the agent receives them.

import praw


def hunt(target_info, credentials, log_queue, results_queue):
    def log(message):
        log_queue.put(f"[REDDIT AGENT]: {message}")

    subreddit_name = target_info.get("target")
    keywords = target_info.get("keywords")
    reddit_creds = credentials.get("reddit_creds")

    # --- NEW DEBUG LOG ---
    # This is the most important check. What did this agent actually receive?
    print(f"[DEBUG] reddit_agent: Received credentials bundle: {reddit_creds}")

    log(f"Sweeping r/{subreddit_name} for keywords: '{keywords}'...")

    # The original check remains the same
    if not reddit_creds or not all(
        k in reddit_creds for k in ["client_id", "client_secret", "user_agent"]
    ):
        log("ERROR: Reddit API credentials not fully configured or received.")
        return

    # ... (rest of the function) ...
    try:
        reddit = praw.Reddit(**reddit_creds)
        # ... search logic ...
    except Exception as e:
        log(f"FATAL ERROR: {e}")
