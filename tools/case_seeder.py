# tools/case_seeder.py

# ==========================================================
# Hunter's Command Console - Case Seeder Utility
# This is a one-time use script to populate the 'cases' table
# with a diverse set of real, live data for GUI testing.
# ==========================================================

import os
import sys

# --- Pathing Magic ---
# This tells the script to look one directory up (to the main project root)
# so it can find our 'hunter' package.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager
from hunter import actions_news_search
import queue


def seed_cases_with_live_data(reddit_count=10, other_count=10):
    """
    Runs the live search agents and seeds the database with a diverse
    set of leads for testing purposes.
    """
    print("[CASE SEEDER]: Dispatching agents to find live test data...")

    # We need a dummy log_queue for the search function to write to.
    log_queue = queue.Queue()

    # Run the full search to get a list of all available leads.
    all_leads = actions_news_search.search_all_sources(log_queue)

    if not all_leads:
        print("[CASE SEEDER ERROR]: No leads were found by any agents. Aborting.")
        return

    print(
        f"[CASE SEEDER]: Agents returned with {len(all_leads)} total leads. Filtering for test data..."
    )

    reddit_leads = []
    other_leads = []

    # Separate the leads into two buckets based on the source.
    for lead in all_leads:
        if (
            "reddit" in lead.get("source", "").lower()
            and len(reddit_leads) < reddit_count
        ):
            reddit_leads.append(lead)
        elif (
            "reddit" not in lead.get("source", "").lower()
            and len(other_leads) < other_count
        ):
            other_leads.append(lead)

    # Combine the buckets to get our final list.
    leads_to_add = reddit_leads + other_leads

    if not leads_to_add:
        print("[CASE SEEDER]: Could not find a suitable mix of leads to add. Aborting.")
        return

    print(f"[CASE SEEDER]: Seeding database with {len(leads_to_add)} cases...")

    successful_adds = 0
    for lead in leads_to_add:
        # We call our existing db_manager function to file the case.
        case_id = db_manager.add_case(lead)
        if case_id:
            successful_adds += 1

    print(
        f"[CASE SEEDER]: Seeding complete. Successfully added {successful_adds} new cases to the database."
    )


if __name__ == "__main__":
    # Make sure you have your API keys in config.ini for this to work!
    seed_cases_with_live_data()
