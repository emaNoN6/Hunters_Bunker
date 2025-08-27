# ==========================================================
# Hunter's Command Console - Reddit Foreman (Corrected)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

from datetime import datetime, timezone
from search_agents import reddit_agent


def run_hunt(log_queue, source, credentials):
	"""
	Manages a hunt on a Reddit source. It deploys an agent, receives the
	raw intel, and translates it into Standardized Lead Reports.

	Args:
		log_queue: The queue for logging messages.
		source (dict): The source record from the database.
		credentials (dict): The API credentials for Reddit.

	Returns:
		(list, str): A tuple containing a list of Standardized Lead Reports
					 and the newest_id_found for bookmarking.
	"""
	# 1. Deploy the agent to get the raw intel
	raw_submissions, newest_id_found = reddit_agent.hunt(log_queue, source, credentials)

	if raw_submissions is None:
		# The hunt itself failed
		return [], None

	# 2. Translate the raw intel into standardized reports
	standardized_reports = []
	for submission in raw_submissions:
		report = _translate_submission(submission, source['id'], source['source_name'])
		if report:
			standardized_reports.append(report)

	return standardized_reports, newest_id_found


def _translate_submission(raw_submission, source_id, source_name):
	"""
	Translates a single raw PRAW Submission object into a Standardized Lead Report.
	This is a private helper function for the foreman.
	"""
	try:
		publication_date = datetime.fromtimestamp(raw_submission.created_utc, tz=timezone.utc)

		standardized_report = {
			"title":            raw_submission.title,
			"url":              f"https://www.reddit.com{raw_submission.permalink}",
			"publication_date": publication_date,
			"text_content":     raw_submission.selftext,
			"html_content":     raw_submission.selftext_html,
			"source_id":        source_id,
			"source_name":      source_name,
			"triage_metadata":  {
				"reddit_score":        raw_submission.score,
				"reddit_upvote_ratio": raw_submission.upvote_ratio,
				"reddit_num_comments": raw_submission.num_comments,
				"is_oc":               raw_submission.is_original_content
			},
			"raw_data_payload": raw_submission
		}
		return standardized_report
	except Exception as e:
		print(f"[REDDIT_FOREMAN ERROR]: Failed to translate submission '{getattr(raw_submission, 'id', 'N/A')}': {e}")
		return None
