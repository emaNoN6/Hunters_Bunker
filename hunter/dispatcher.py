# ==========================================================
# Hunter's Command Console - Definitive Dispatcher
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import importlib
from . import db_manager, filing_clerk, config_manager


def run_hunt(log_queue):
	"""
	The main dispatcher function. Kicks off a full intel-gathering sweep.
	This is the function your "Check for New Cases" button will call.
	"""
	log_queue.put("[DISPATCHER]: Waking up. Getting mission roster...")

	active_sources = db_manager.get_active_sources_by_purpose('lead_generation')
	if not active_sources:
		log_queue.put("[DISPATCHER]: No active sources found. Standing down.")
		return

	# For now, we'll run agents serially. "Dispatcher v2" will handle concurrency.
	for source in active_sources:
		source_name = source['source_name']
		agent_type = source['agent_type']

		log_queue.put(f"[DISPATCHER]: Summoning foreman for '{agent_type}' to hunt source '{source_name}'...")

		try:
			# Dynamically import the correct foreman module
			foreman_module = importlib.import_module(f"hunter.foremen.{agent_type}_foreman")

			# Get credentials directly from the config manager based on agent_type.
			# This keeps the db_manager clean of credential logic.
			credentials = {}
			match(agent_type):
				case 'reddit':
					credentials = config_manager.get_reddit_credentials()
				case 'gnews_io':
					credentials = config_manager.get_gnews_io_credentials()
				case _:
					credentials = {}

			# --- The Hunt ---
			standardized_reports, newest_id = foreman_module.run_hunt(log_queue, source, credentials)

			# --- After-Action Report ---
			if standardized_reports is not None:  # A successful hunt (even with 0 leads)
				hunt_results = {
					'success':         True,
					'new_bookmark_id': newest_id
				}
				# Hand off the clean reports to the Filing Clerk
				for report in standardized_reports:
					filing_clerk.file_new_lead(log_queue, report)
			else:  # The hunt function returned an error
				hunt_results = {'success': False}

			# File the after-action report on the source's status
			db_manager.update_source_state(source['id'], hunt_results)

		except ImportError:
			log_queue.put(f"[DISPATCHER ERROR]: Could not find foreman module for type '{agent_type}'. Skipping.")
			db_manager.update_source_state(source['id'], {'success': False})
			continue
		except Exception as e:
			log_queue.put(
				f"[DISPATCHER ERROR]: A critical error occurred while running foreman for '{source_name}': {e}")
			db_manager.update_source_state(source['id'], {'success': False})

	log_queue.put("[DISPATCHER]: All hunts complete. Standing by.")

