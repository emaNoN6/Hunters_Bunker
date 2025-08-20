# ==========================================================
# Hunter's Command Console - Definitive Dispatcher
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import importlib
from . import db_manager, db_admin, config_manager


def run_hunt(log_queue):
	"""
	The main dispatcher function. Kicks off a full intel-gathering sweep.
	This is the function your "Check for New Cases" button will call.
	"""
	log_queue.put("[DISPATCHER]: Waking up. Getting mission roster...")

	active_sources = db_manager.get_active_lead_sources()
	if not active_sources:
		log_queue.put("[DISPATCHER]: No active sources found. Standing down.")
		return

	# For now, we'll run agents serially. "Dispatcher v2" will handle concurrency.
	for source in active_sources:
		source_name = source['source_name']
		agent_type = source['agent_type']

		log_queue.put(f"[DISPATCHER]: Deploying agent '{agent_type}' for source '{source_name}'...")

		try:
			# Dynamically import the correct agent module
			agent_module = importlib.import_module(f"search_agents.{agent_type}_agent")

			# Get the necessary credentials for this agent's domain
			credentials = {}
			if agent_type == 'reddit':
				credentials = config_manager.get_reddit_credentials()
			elif agent_type == 'gnews_io':
				credentials = config_manager.get_gnews_io_credentials()

			# --- The Hunt ---
			leads, newest_id = agent_module.hunt(log_queue, source, credentials)

			# --- After-Action Report ---
			if leads is not None:  # A successful hunt (even with 0 leads)
				hunt_results = {
					'success':         True,
					'new_bookmark_id': newest_id
				}
				# Log the new leads
				for lead in leads:
					db_manager.log_acquisition(lead, source['id'])
			else:  # The hunt function returned an error
				hunt_results = {'success': False}

			# File the report
			db_manager.update_source_state(source['id'], hunt_results)

		except ImportError:
			log_queue.put(f"[DISPATCHER ERROR]: Could not find agent module for type '{agent_type}'. Skipping.")
			continue
		except Exception as e:
			log_queue.put(f"[DISPATCHER ERROR]: A critical error occurred while running agent for '{source_name}': {e}")
			db_manager.update_source_state(source['id'], {'success': False})

	log_queue.put("[DISPATCHER]: All hunts complete. Standing by.")

