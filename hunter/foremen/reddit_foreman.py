# foremen/reddit_foreman.py

import logging
from datetime import datetime, timezone
from search_agents import reddit_agent

logger = logging.getLogger("Reddit Foreman")


def run_hunt(source, credentials):
	"""
	Manages the hunt for a specific Reddit source.
	It deploys the agent, then translates the raw results.
	"""
	logger.info(f"[{source.get('source_name')}]: Deploying agent to hunt r/{source.get('target')}")

	try:
		raw_submissions, newest_id = reddit_agent.hunt(source, credentials)

		if raw_submissions is None:
			logger.error(f"[{source.get('source_name')}]: Hunt failed critically. Agent returned None.")
			return [], None

		logger.info(
			f"[{source.get('source_name')}]: Agent returned with {len(raw_submissions)} submissions. Translating...")

		clean_leads = []
		for submission in raw_submissions:
			translated_lead = _translate_submission(submission, source)
			if translated_lead:
				clean_leads.append(translated_lead)

		return clean_leads, newest_id

	except Exception:
		logger.error(f"A critical error occurred while running foreman for '{source.get('source_name')}'",
		             exc_info=True)
		return [], None


def _translate_submission(submission, source):
	"""
	Translates a raw PRAW Submission object into our Standardized Lead Report.
	This version is more robust and handles missing data gracefully.
	"""
	try:
		# --- THIS IS THE FIX ---
		# 1. Be paranoid about the URL. Use the main URL, but if it's missing or
		#    points to the comments, fall back to the full permalink.
		url = submission.url
		if not url or 'reddit.com' in url:
			url = f"https://www.reddit.com{submission.permalink}"

		# 2. Ensure publication_date is always a valid datetime object.
		#    PRAW's created_utc is a Unix timestamp.
		pub_date = datetime.fromtimestamp(submission.created_utc, tz=timezone.utc)

		# 3. Build the Triage Metadata dictionary safely, using .get() with defaults.
		triage_meta = {
			"reddit_score":        getattr(submission, 'score', 0),
			"reddit_upvote_ratio": getattr(submission, 'upvote_ratio', 0.0),
			"reddit_num_comments": getattr(submission, 'num_comments', 0),
			"reddit_is_oc":        getattr(submission, 'is_original_content', False)
		}
		# --- END FIX ---

		standardized_report = {
			"title":            submission.title,
			"url":              url,
			"publication_date": pub_date,
			"text_content":     submission.selftext,
			"html_content":     submission.selftext_html,
			"source_id":        source.get('id'),
			"source_name":      source.get('source_name'),
			"triage_metadata":  triage_meta,
		}
		return standardized_report

	except Exception:
		# If a single submission is corrupted, log it and move on.
		# This prevents one bad post from crashing the whole hunt.
		submission_id = getattr(submission, 'id', 'N/A')
		logger.error(f"Failed to translate submission '{submission_id}'", exc_info=True)
		return None
