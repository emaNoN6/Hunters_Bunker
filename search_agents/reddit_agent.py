# ==========================================================
# Hunter's Command Console - Definitive Reddit Agent (Corrected)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import praw
import time
import logging
logger = logging.getLogger("Reddit Agent")

def hunt(source, credentials):
	"""
	Hunts a subreddit for new posts and returns the RAW PRAW Submission objects.
	The Foreman is responsible for translation.
	"""
	subreddit_name = source.get('target')
	last_known_id = source.get('last_known_item_id')
	source_name = source.get('source_name')

	logger.info(f"[{source_name}]: Waking up. Patrolling r/{subreddit_name}...")

	if not credentials:
		logger.error(f"[{source_name} ERROR]: Reddit API credentials not provided.")
		return [], None

	raw_submissions = []
	newest_id_found = None

	try:
		reddit = praw.Reddit(
				client_id=credentials['client_id'],
				client_secret=credentials['client_secret'],
				user_agent=credentials['user_agent']
		)

		# --- Rate Limit Check ---
		# This check is safe and provides good intel for us.
		if reddit.auth.limits:
			remaining = reddit.auth.limits.get('remaining')
			reset_timestamp = reddit.auth.limits.get('reset_timestamp')
			if reset_timestamp:
				reset_seconds = reset_timestamp - time.time()
				logger.warning(
					f"[{source_name}]: Rate Limit Status: {remaining} requests remaining. Reset in {int(reset_seconds)} seconds.")
		# --- End Rate Limit Check ---

		subreddit = reddit.subreddit(subreddit_name)

		for submission in subreddit.new(limit=100):
			if newest_id_found is None:
				newest_id_found = submission.id

			if submission.id == last_known_id:
				logger.info(f"[{source_name}]: Found bookmark ({last_known_id}). Concluding hunt.")
				break

			if submission.stickied or not submission.is_self:
				continue

			# --- THIS IS THE FIX ---
			# The agent's only job is to gather the raw intel.
			# We append the entire, untouched submission object.
			raw_submissions.append(submission)
		# --- END FIX ---

		# Reverse the list to process oldest-first
		raw_submissions.reverse()

		logger.info(f"[{source_name}]: Hunt successful. Returned {len(raw_submissions)} raw submissions.")

		return raw_submissions, newest_id_found

	except Exception as e:
		logger.error(f"[{source_name} ERROR]: An error occurred during the hunt: {e}")
		return [], None
