# ==========================================================
# Hunter's Command Console - Definitive Reddit Agent (v2)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import praw
import time
from datetime import datetime, timezone


def hunt(log_queue, source, credentials):
	"""
	Hunts a subreddit for new posts since the last check, using the
	last_known_item_id as a bookmark.
	"""
	subreddit_name = source.get('target')
	last_known_id = source.get('last_known_item_id')
	source_name = source.get('source_name')

	log_queue.put(f"[{source_name}]: Waking up. Patrolling r/{subreddit_name}...")

	if not credentials:
		log_queue.put(f"[{source_name} ERROR]: Reddit API credentials not provided.")
		return [], None

	leads = []
	newest_id_found = None

	try:
		reddit = praw.Reddit(
				client_id=credentials['client_id'],
				client_secret=credentials['client_secret'],
				user_agent=credentials['user_agent']
		)
		subreddit = reddit.subreddit(subreddit_name)

		# --- Rate Limit Check ---
		if reddit.auth.limits:
			remaining = reddit.auth.limits.get('remaining')
			reset_timestamp = reddit.auth.limits.get('reset_timestamp')
			if reset_timestamp:
				reset_seconds = reset_timestamp - time.time()
				log_queue.put(
					f"[{source_name}]: Rate Limit Status: {remaining} requests remaining. Reset in {int(reset_seconds)} seconds.")
			else:
				log_queue.put(
					f"[{source_name}]: Rate Limit Status: {remaining} requests remaining. Reset time not available yet.")
		# --- End Rate Limit Check ---

		log_queue.put(f"[{source_name}]: Looking for posts newer than bookmark: {last_known_id}")

		for submission in subreddit.new(limit=100):
			if newest_id_found is None:
				newest_id_found = submission.id

			if submission.id == last_known_id:
				log_queue.put(f"[{source_name}]: Found bookmark ({last_known_id}). Concluding hunt.")
				break

			if submission.stickied or not submission.is_self:
				continue

			publication_date = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)

			lead_data = {
				"title":            submission.title,
				"url":              f"https://www.reddit.com{submission.permalink}",
				"text":             submission.selftext,
				"html":             submission.selftext_html,
				"publication_date": publication_date,
				"source_name":      source_name,
				"score":            submission.score,
				"upvote_ratio":     submission.upvote_ratio,
				"num_comments":     submission.num_comments,
				"is_oc":            submission.is_original_content
			}
			leads.append(lead_data)

		leads.reverse()

		log_queue.put(f"[{source_name}]: Hunt successful. Returned {len(leads)} new leads.")

		return leads, newest_id_found

	except Exception as e:
		log_queue.put(f"[{source_name} ERROR]: An error occurred during the hunt: {e}")
		return [], None
