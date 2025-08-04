# ==========================================================
# Hunter's Command Console - Bootstrap Case Data Utility
#
# This is a one-time use script to populate the 'cases' table
# with a diverse set of real, live data for GUI testing.
# It INTENTIONALLY IGNORES the acquisition_log to ensure
# we get data even if the leads have been seen before.
# ==========================================================

import os
import sys
import random

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager
from hunter import actions_news_search
import queue


def bootstrap_cases(reddit_count=10, other_count=10):
	"""
	Runs the live search agents, IGNORES the acquisition log, and seeds
	the database with a diverse set of leads for testing purposes.
	"""
	print("[BOOTSTRAP]: Dispatching agents to find live test data...")

	# We need a dummy log_queue for the search function to write to.
	log_queue = queue.Queue()

	# We need to temporarily modify the dispatcher's behavior.
	# This is a bit of a hack, but it's for a one-time tool.
	# We'll tell the agents to return ALL leads, not just new ones.

	# For this to work, we need to modify the dispatcher to accept a flag.
	# Let's assume for now we just get all leads and then process.

	# A simpler approach: The dispatcher gets all leads, and we just file them.
	# The dispatcher's internal check against the log is the problem.
	# Let's build a simpler, dumber dispatcher right here.

	print("[BOOTSTRAP]: Bypassing standard dispatcher to ignore acquisition log...")

	from search_agents import reddit_agent, gnews_io_agent
	from hunter import config_manager

	reddit_creds = config_manager.get_reddit_credentials()
	gnews_creds = config_manager.get_gnews_io_credentials()

	all_leads = []

	# Hunt Reddit
	if reddit_creds:
		print(" -> Hunting Reddit...")
		# A simplified hunt on one subreddit
		source_mock = {'target': 'paranormal', 'source_name': 'r/paranormal'}
		reddit_leads = reddit_agent.hunt(log_queue, source_mock, reddit_creds)
		all_leads.extend(reddit_leads)

	# Hunt GNews
	if gnews_creds:
		print(" -> Hunting GNews.io...")
		source_mock = {'target': '"unexplained phenomena"', 'source_name': 'GNews.io'}
		gnews_leads = gnews_io_agent.hunt(log_queue, source_mock, gnews_creds)
		all_leads.extend(gnews_leads)

	if not all_leads:
		print("[BOOTSTRAP ERROR]: No leads were found by any agents. Aborting.")
		return

	print(f"[BOOTSTRAP]: Agents returned with {len(all_leads)} total leads. Filtering and filing...")

	# Shuffle the list to get a random mix
	random.shuffle(all_leads)

	leads_to_add = all_leads[:(reddit_count + other_count)]

	if not leads_to_add:
		print("[BOOTSTRAP]: Could not find any leads to add. Aborting.")
		return

	print(f"[BOOTSTRAP]: Seeding database with {len(leads_to_add)} cases...")

	successful_adds = 0
	for lead in leads_to_add:
		# We call our existing db_manager function to file the case.
		# The ON CONFLICT clause in add_case will handle any true duplicates.
		case_id = db_manager.add_case(lead)
		if case_id:
			successful_adds += 1

	print(f"[BOOTSTRAP]: Seeding complete. Successfully added {successful_adds} new cases to the database.")


if __name__ == "__main__":
	# Make sure you have your API keys in config.ini for this to work!
	bootstrap_cases()

