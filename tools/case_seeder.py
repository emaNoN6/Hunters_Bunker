# ==========================================================
# Hunter's Command Console - Definitive Case Seeder
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import os
import sys
import random
import queue
import time

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager, config_manager, db_admin
from hunter.utils import start_console_log_consumer
from search_agents import reddit_agent, gnews_io_agent


def setup_seed_sources(log_queue):
	"""
	Ensures the necessary source_domains and sources for seeding exist in the DB.
	"""
	log_queue.put("[SEEDER]: Verifying seed sources exist...")

	required_sources = {
		"Reddit Paranormal":    {
			"domain_name": "reddit.com", "agent_type": "reddit", "target": "paranormal"
		},
		"GNews.io Unexplained": {
			"domain_name": "gnews.io", "agent_type": "gnews", "target": '"unexplained phenomena"'
		}
	}

	db_admin.add_source_domain({"domain_name": "reddit.com", "agent_type": "reddit"})
	db_admin.add_source_domain({"domain_name": "gnews.io", "agent_type": "gnews"})

	live_sources = {}
	for name, data in required_sources.items():
		data['source_name'] = name
		db_admin.add_source(data)
		source_info = db_manager.get_source_by_name(name)
		if source_info:
			live_sources[name] = source_info
		else:
			log_queue.put(f"[SEEDER ERROR]: Failed to create or find source '{name}'. Aborting.")
			return None

	log_queue.put("[SEEDER]: All seed sources are configured in the database.")
	return live_sources


def seed_cases(log_queue, count=20):
	"""
	Runs live search agents and correctly seeds the database.
	"""
	live_sources = setup_seed_sources(log_queue)
	if not live_sources:
		return

	reddit_creds = config_manager.get_reddit_credentials()
	gnews_creds = config_manager.get_gnews_io_credentials()

	all_leads = []

	# Hunt Reddit
	if reddit_creds and "Reddit Paranormal" in live_sources:
		log_queue.put(" -> Hunting Reddit for fresh intel...")
		reddit_source = live_sources["Reddit Paranormal"]
		reddit_leads, _ = reddit_agent.hunt(log_queue, reddit_source, reddit_creds)
		for lead in reddit_leads:
			# --- THIS IS THE FIX ---
			# Attach the full source intel to the lead
			lead['source_id'] = reddit_source['id']
			lead['source_name'] = reddit_source['source_name']
		# --- END FIX ---
		all_leads.extend(reddit_leads)

	# Hunt GNews
	if gnews_creds and "GNews.io Unexplained" in live_sources:
		log_queue.put(" -> Hunting GNews.io for fresh intel...")
		gnews_source = live_sources["GNews.io Unexplained"]
		gnews_leads, _ = gnews_io_agent.hunt(log_queue, gnews_source, gnews_creds)
		for lead in gnews_leads:
			# --- THIS IS THE FIX ---
			# Attach the full source intel to the lead
			lead['source_id'] = gnews_source['id']
			lead['source_name'] = gnews_source['source_name']
		# --- END FIX ---
		all_leads.extend(gnews_leads)

	if not all_leads:
		log_queue.put("[SEEDER ERROR]: No leads were found by any agents. Aborting.")
		return

	log_queue.put(f"[SEEDER]: Agents returned with {len(all_leads)} total leads. Filtering and filing...")

	random.shuffle(all_leads)
	leads_to_add = all_leads[:count]

	log_queue.put(f"[SEEDER]: Seeding database with {len(leads_to_add)} cases...")

	successful_adds = 0
	for lead in leads_to_add:
		if not lead.get("publication_date"):
			log_queue.put(f"[SEEDER WARNING]: Skipping lead '{lead.get('title')}' due to missing publication_date.")
			continue

		lead_uuid = db_manager.log_acquisition(lead, lead['source_id'])
		if not lead_uuid:
			log_queue.put(f"[SEEDER WARNING]: Failed to log lead '{lead.get('title')}'. Skipping.")
			continue

		lead['lead_uuid'] = lead_uuid
		case_id = db_manager.add_case(lead)
		if case_id:
			successful_adds += 1

	log_queue.put(f"[SEEDER]: Seeding complete. Successfully added {successful_adds} new cases.")


if __name__ == "__main__":
	log_queue = queue.Queue()
	start_console_log_consumer(log_queue)
	seed_cases(log_queue)
	time.sleep(1)
