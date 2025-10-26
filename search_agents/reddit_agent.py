# ==========================================================
# Hunter's Command Console - Reddit Agent (v2 - Simplified)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================
import praw
import logging
from datetime import datetime, timezone

logger = logging.getLogger("Reddit Agent")


def hunt(source, credentials):
	"""
	Hunts a specific subreddit for new posts since the last check.
	This agent's sole responsibility is to fetch the raw post data.
	All translation and data formatting is handled by the RedditForeman.
	"""
	subreddit_name = source.get('target')
	last_checked_id = source.get('last_checked_id')
	source_name = source.get('source_name')

	logger.info(f"[{source_name}]: Waking up. Hunting r/{subreddit_name}...")

	if not all([
		credentials,
		credentials.get('client_id'),
		credentials.get('client_secret'),
		credentials.get('user_agent')
	]):
		logger.error(f"[{source_name} ERROR]: Reddit API credentials are incomplete.")
		return [], None

	try:
		reddit = praw.Reddit(
				client_id=credentials['client_id'],
				client_secret=credentials['client_secret'],
				user_agent=credentials['user_agent']
		)
		subreddit = reddit.subreddit(subreddit_name)

		# PRAW handles the logic of fetching only new posts since the last one seen.
		# It's more efficient than using timestamps.
		params = {'before': last_checked_id} if last_checked_id else {}

		# We fetch a reasonable limit. The foreman will process them.
		new_posts = list(subreddit.new(limit=50, params=params))

		if not new_posts:
			logger.info(f"[{source_name}]: No new posts found in r/{subreddit_name}.")
			return [], last_checked_id

		# The agent's job is to return the raw, unprocessed data.
		# We extract the necessary attributes into a simple dictionary.
		# The foreman is responsible for turning this into a LeadData object.
		raw_leads = []
		for post in new_posts:
			raw_leads.append({
				"title":        post.title,
				"url":          post.url,
				"id":           post.id,
				"subreddit":    post.subreddit.display_name,
				"author":       post.author.name if post.author else "[deleted]",
				"created_utc":  post.created_utc,
				"score":        post.score,
				"num_comments": post.num_comments,
				"is_self":      post.is_self,
				"selftext":     post.selftext,
			})

		# The newest post is the first one in the list returned by .new()
		newest_id = new_posts[0].id

		logger.info(
				f"[{source_name}]: Hunt successful. Returned {len(raw_leads)} new raw leads. Newest ID: {newest_id}")
		return raw_leads, newest_id

	except Exception as e:
		logger.error(f"[{source_name} ERROR]: An error occurred during the hunt for r/{subreddit_name}: {e}",
		             exc_info=True)
		return [], last_checked_id
