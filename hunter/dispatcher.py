# ==========================================================
# Hunter's Command Console - Dispatcher (v4 - Corrected)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import importlib
import logging
import threading
import inspect
from pathlib import Path
from hunter.models import SourceConfig

from sympy.strategies.core import switch

# --- Our Tools ---
from hunter import db_manager  # Import the module itself
from hunter.filing_clerk import FilingClerk

logger = logging.getLogger("Dispatcher")


def _build_foreman_map(conn):  # <-- FIX: Takes the connection object, named 'conn'
	"""
	Dynamically builds the foreman map by validating required foremen
	against the filesystem.
	"""
	# Step 1: Get the REQUIRED list from the database.
	# This call now correctly uses the imported 'db_manager' module.
	required_foremen = db_manager.get_required_foremen(conn)
	if not required_foremen:
		logger.warning("No required foremen found in the database view 'foreman_agents'.")
		return {}

	logger.info(f"Database requires foremen: {required_foremen}")

	# Step 2: Scan the filesystem to see what foremen are AVAILABLE.
	foreman_map = {}
	foreman_dir = Path(__file__).parent / 'foremen'
	for f in foreman_dir.glob('*.py'):
		if f.name.startswith('__'): continue
		module_name = f.stem
		try:
			module = importlib.import_module(f"hunter.foremen.{module_name}")
			handler = None
			for name, obj in inspect.getmembers(module):
				if inspect.isclass(obj) and name.endswith('Foreman'):
					handler = obj  # New class-based foreman
					break
			if not handler:
				handler = module  # Old function-based foreman
			foreman_map[module_name] = handler
		except ImportError as e:
			logger.error(f"Failed to import foreman module {module_name}: {e}")

	# Step 3: Validate that all REQUIRED foremen are AVAILABLE.
	for req in required_foremen:
		if req not in foreman_map:
			# This is our Python version of crash_and_burn()
			error_msg = f"CRITICAL BOOTSTRAP FAILED: Database requires foreman '{req}', but file 'hunter/foremen/{req}.py' was not found or failed to import."
			logger.critical(error_msg)
			raise ImportError(error_msg)

	logger.info("All required foremen are present. Foreman map built successfully.")
	return foreman_map


class Dispatcher:
	# FIX: The first argument is now unambiguously named 'db_conn'.
	def __init__(self, db_conn, config):
		self.db_conn = db_conn  # <-- FIX: The connection object
		self.config = config
		self.filing_clerk = FilingClerk(db_conn)
		self.active_threads = {}
		# This now correctly passes the connection object to the builder.
		self.foreman_map = _build_foreman_map(self.db_conn)

	def dispatch(self, sources):
		threads = []
		self.all_threads_done = threading.Event()  # Create event flag

		for source in sources:
			source_config = SourceConfig(**source)
			thread = threading.Thread(target=self._dispatch_source, args=(source_config,))
			self.active_threads[source_config.source_name] = thread
			threads.append(thread)
			thread.start()

		# Start a watcher thread that sets the event when all workers finish
		def wait_for_all():
			for thread_loop in threads:
				thread_loop.join()
			self.all_threads_done.set()  # Signal that all threads are done

		watcher = threading.Thread(target=wait_for_all)
		watcher.start()
		return self.all_threads_done

	def _dispatch_source(self, source_config: SourceConfig):
		source_name = source_config.source_name
		agent_type = source_config.agent_type  # From the VIEW/JOIN

		if not all([source_name, agent_type]):
			logger.error(f"Source is missing required configuration (name or agent_type).")
			return

		logger.info(f"Dispatching hunt for source: {source_name}")

		try:
			# --- AGENT MODULE ---
			agent_module_name = agent_type  # Convention: agent_type matches agent .py file name
			agent_module = importlib.import_module(f"search_agents.{agent_module_name}_agent")
			credentials = None
			logger.info(f"Getting credentials for: {agent_module_name}")
			match agent_module_name:
				case 'reddit':
					credentials = self.config.get_reddit_credentials()
				case 'gnews_io':
					credentials = self.config.get_gnews_io_credentials()

			raw_leads, bookmark = agent_module.hunt(source_config, credentials)

			if not raw_leads:
				logger.info(f"Agent for '{source_name}' returned no new leads.")
				return

			# --- FOREMAN MODULE ---
			foreman_name = f"{agent_type}_foreman"
			foreman_handler = self.foreman_map.get(foreman_name)
			if not foreman_handler:
				# This should be caught at startup, but is a good runtime safety check.
				logger.error(f"No foreman found for '{foreman_name}'.")
				return

			processed_leads = []
			if inspect.isclass(foreman_handler):
				foreman_instance = foreman_handler(source_config)
				processed_leads = foreman_instance.translate_leads(raw_leads)
			else:  # Fallback for old function-based foremen
				processed_leads = foreman_handler.translate(raw_leads, source_name)

			if not processed_leads:
				logger.warning(f"Foreman for '{source_name}' processed {len(raw_leads)} raw leads into 0 valid leads.")
				return

			# --- FILING CLERK ---
			logger.info(f"Handing off {len(processed_leads)} leads from '{source_name}' to Filing Clerk.")
			self.filing_clerk.file_leads(processed_leads)

			# --- UPDATE SOURCE STATE ---
			# You'll need a function in db_manager to update the last_checked time, etc.
			# db_manager.update_source_state(self.db_conn, source_config['id'], success=True, new_bookmark=bookmark)

		except ImportError as e:
			logger.error(f"Failed to import module for source '{source_name}': {e}")
		except Exception as e:
			logger.critical(f"An unexpected error occurred in the dispatch loop for '{source_name}': {e}",
			                exc_info=True)
		finally:
			if source_name in self.active_threads:
				del self.active_threads[source_name]
