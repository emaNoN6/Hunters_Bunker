# This version now correctly provides both plain text for the AI
# and clean HTML for the viewer.

import praw


def hunt(target_info, credentials, log_queue, results_queue):
    def log(message):
        log_queue.put(f"[REDDIT AGENT]: {message}")

    subreddit_name = target_info.get("target")
    reddit_creds = credentials.get("reddit_creds")

    log(f"Sweeping r/{subreddit_name} for new posts...")

    if not reddit_creds or not all(
        k in reddit_creds for k in ["client_id", "client_secret", "user_agent"]
    ):
        log("ERROR: Reddit API credentials not fully configured.")
        return

    try:
        reddit = praw.Reddit(**reddit_creds)
        subreddit = reddit.subreddit(subreddit_name)

        # We'll just grab the newest posts for now.
        for submission in subreddit.new(limit=25):
            # --- THE UPGRADE ---
            # We now create a lead dictionary with both text and html.
            lead = {
                "source": f"Reddit (r/{subreddit_name})",
                "title": submission.title,
                "url": f"https://reddit.com{submission.permalink}",
                "text": f"{submission.title}\n\n{submission.selftext}",  # For the AI model
                "html": submission.selftext_html,  # For the GUI viewer
            }
            results_queue.put(lead)

        log(f"Sweep complete for r/{subreddit_name}.")

    except Exception as e:
        log(f"FATAL ERROR: Could not connect or search r/{subreddit_name} - {e}")
