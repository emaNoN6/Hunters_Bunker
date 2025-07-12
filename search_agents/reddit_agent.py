# search_agents/reddit_agent.py

import praw
from hunter import db_manager
from hunter import config_manager


def hunt(log_queue, source):
    """
    Searches for new posts in a given subreddit.
    """
    subreddit_name = source.get("target")
    source_id = source.get("id")
    source_name = source.get("source_name")

    log_queue.put(f"[{source_name}]: Waking up. Patrolling r/{subreddit_name}...")

    reddit_creds = config_manager.get_reddit_credentials()
    if not reddit_creds:
        log_queue.put(
            f"[{source_name} ERROR]: Reddit API credentials not found in config.ini"
        )
        return []

    results = []
    try:
        reddit = praw.Reddit(
            client_id=reddit_creds["client_id"],
            client_secret=reddit_creds["client_secret"],
            user_agent=reddit_creds["user_agent"],
        )

        subreddit = reddit.subreddit(subreddit_name)

        # We only look at the 25 newest posts to keep the search fast.
        for submission in subreddit.new(limit=25):
            # Check if we've already processed this post
            if db_manager.check_acquisition_log(submission.url):
                continue

            lead_data = {
                "title": submission.title,
                "url": submission.url,
                "source": f"r/{subreddit_name}",
                "text": submission.selftext,
                "html": f"<h1>{submission.title}</h1><p>{submission.selftext_html}</p>",
            }
            results.append(lead_data)
            db_manager.log_acquisition(
                submission.url, source_id, submission.title, "PROCESSED"
            )

        log_queue.put(f"[{source_name}]: Found {len(results)} new leads.")
        return results

    except Exception as e:
        log_queue.put(f"[{source_name} ERROR]: {e}")
        return []
