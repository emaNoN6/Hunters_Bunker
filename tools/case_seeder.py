# ==========================================================
# Hunter's Command Console - Definitive Case Seeder (Final)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import logging

# --- Centralized Pathing ---
from hunter.utils.path_utils import setup_project_path

setup_project_path()
# --- End Pathing ---

from hunter import db_admin, db_manager, config_manager
from hunter.foremen import reddit_foreman, gnews_io_foreman, test_data_foreman

# Get a logger for this module
logger = logging.getLogger(__name__)


def setup_seed_sources():
	"""
	Ensures the necessary source_domains and sources for seeding exist in the DB.
	"""
	logger.info("Verifying seed sources exist...")

	required_sources = {
		"Reddit Paranormal":    {
			"domain_name": "reddit.com", "agent_type": "reddit", "target": "paranormal"
		},
		"GNews.io Unexplained": {
			"domain_name": "gnews.io", "agent_type": "gnews_io", "target": '"unexplained phenomena"'
		},
		"Test Data Source":     {
			"domain_name": "testdata", "agent_type": "test_data", "target": "test_leads.json"
		}
	}

	# Ensure domains exist first
	db_admin.add_source_domain({"domain_name": "reddit.com", "agent_type": "reddit"})
	db_admin.add_source_domain({"domain_name": "gnews.io", "agent_type": "gnews_io"})
	db_admin.add_source_domain({"domain_name": "testdata", "agent_type": "test_data"})

	# Now, ensure sources exist and get their real DB info
	live_sources = {}
	for name, data in required_sources.items():
		data['source_name'] = name
		db_admin.add_source(data)
		source_info = db_manager.get_source_by_name(name)
		if source_info:
			live_sources[name] = source_info
		else:
			logger.error(f"Failed to create or find source '{name}'. Aborting.")
			return None

	logger.info("All seed sources are configured in the database.")
	return live_sources


def seed_cases(count=20):
	"""
	Runs live hunts via the foremen and seeds the database.
	"""
	live_sources = setup_seed_sources()
	if not live_sources:
		return

	reddit_creds = config_manager.get_reddit_credentials()
	gnews_creds = config_manager.get_gnews_io_credentials()

	all_reports = []

	# --- THIS IS THE FIX ---
	# We now call the FOREMEN, not the agents, and use the REAL source data.

	# Hunt Reddit
	if reddit_creds and "Reddit Paranormal" in live_sources:
		logger.info("Dispatching Reddit Foreman for fresh intel...")
		reddit_source = live_sources["Reddit Paranormal"]
		reports, _ = reddit_foreman.run_hunt(reddit_source, reddit_creds)
		if reports:
			all_reports.extend(reports)

	# Hunt GNews
	if gnews_creds and "GNews.io Unexplained" in live_sources:
		logger.info("Dispatching GNews.io Foreman for fresh intel...")
		gnews_source = live_sources["GNews.io Unexplained"]
		reports, _ = gnews_io_foreman.run_hunt(gnews_source, gnews_creds)
		if reports:
			all_reports.extend(reports)

	# Hunt Test Data
	if "Test Data Source" in live_sources:
		logger.info("Dispatching Test Data Foreman...")
		test_source = live_sources["Test Data Source"]
		reports, _ = test_data_foreman.run_hunt(test_source)
		if reports:
			all_reports.extend(reports)
	# --- END FIX ---

	if not all_reports:
		logger.error("No leads were found by any foremen. Aborting.")
		return

	logger.info(f"Foremen returned with {len(all_reports)} total standardized reports. No filing needed for seeder.")
	logger.info("Seeding complete. Use the main dispatcher to file new leads.")


if __name__ == "__main__":
	from hunter.utils import logger_setup

	logger_setup.setup_logging()
	seed_cases()
