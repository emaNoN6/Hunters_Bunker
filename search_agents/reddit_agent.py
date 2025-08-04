# search_agents/reddit_agent.py

import praw
from hunter import db_manager  # Use relative import


def hunt(log_queue, source, reddit_creds):
	"""
    Searches for new posts in a given subreddit.
    Credentials are now passed in directly by the dispatcher.
    """
	subreddit_name = source.get('target')
	source_id = source.get('id')
	source_name = source.get('source_name')

	log_queue.put(f"[{source_name}]: Waking up. Patrolling r/{subreddit_name}...")

	if not reddit_creds:
		log_queue.put(f"[{source_name} ERROR]: Reddit API credentials were not provided by the dispatcher.")
		return []

	results = []
	try:
		reddit = praw.Reddit(
				client_id=reddit_creds['client_id'],
				client_secret=reddit_creds['client_secret'],
				user_agent=reddit_creds['user_agent']
		)

		subreddit = reddit.subreddit(subreddit_name)

		for submission in subreddit.new(limit=25):
			# The dispatcher now handles checking the acquisition log,
			# so the agent's only job is to gather the intel.
			lead_data = {
				"title":  submission.title,
				"url":    submission.url,
				"source": source_name,  # Use the clean name from the DB
				"text":   submission.selftext,
				"html":   submission.selftext_html if submission.selftext_html else f"<p>{submission.selftext}</p>"
			}
			results.append(lead_data)

		log_queue.put(f"[{source_name}]: Found {len(results)} potential leads.")
		return results

	except Exception as e:
		log_queue.put(f"[{source_name} ERROR]: {e}")
		return []
