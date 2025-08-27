# ==========================================================
# Hunter's Command Console - Reddit Foreman (Hardened)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

from datetime import datetime, timezone
from search_agents import reddit_agent


def run_hunt(log_queue, source, credentials):
	"""
	Manages a hunt on a Reddit source. It deploys an agent, receives the
	raw intel, and translates it into Standardized Lead Reports.
	Includes robust error handling.
	"""
	# --- THIS IS THE FIX: The Safety Net ---
	try:
		# 1. Deploy the agent to get the raw intel
		raw_submissions, newest_id_found = reddit_agent.hunt(log_queue, source, credentials)
	except Exception as e:
		# If the agent itself crashes, we catch it here.
		log_queue.put(f"[REDDIT_FOREMAN ERROR]: The hunt conducted by the agent failed critically: {e}")
		return None, None  # Signal a failure to the dispatcher
	# --- END FIX ---

	if raw_submissions is None:
		# The hunt function returned an error state
		return None, None

	# 2. Translate the raw intel into standardized reports
	standardized_reports = []
	for submission in raw_submissions:
		report = _translate_submission(submission, source['id'], source['source_name'], log_queue)
		if report:
			standardized_reports.append(report)

	return standardized_reports, newest_id_found


def _translate_submission(raw_submission, source_id, source_name, log_queue):
	"""
	Translates a single raw PRAW Submission object into a Standardized Lead Report.
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
			}
			# --- THIS IS THE FIX: No more raw payload ---
			# "raw_data_payload": raw_submission # Removed
		}
		return standardized_report
	except Exception as e:
		log_queue.put(f"[REDDIT_FOREMAN ERROR]: Failed to translate submission '{getattr(raw_submission, 'id', 'N/A')}': {e}")
		return None
