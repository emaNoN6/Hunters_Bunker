# ==========================================================
# Hunter's Command Console - Dispatcher (v4.1 - State Fixed)
# ==========================================================

import importlib
import logging
import threading
import inspect
from pathlib import Path
from hunter.models import SourceConfig

# --- Our Tools ---
from hunter import db_manager
from hunter.filing_clerk import FilingClerk

logger = logging.getLogger("Dispatcher")


def _build_foreman_map():
	"""Dynamically builds the foreman map."""
	required_foremen = db_manager.get_required_foremen()
	if not required_foremen:
		logger.warning("No required foremen found in the database.")
		return {}

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
					handler = obj
					break
			if not handler:
				handler = module
			foreman_map[module_name] = handler
		except ImportError as e:
			logger.error(f"Failed to import foreman module {module_name}: {e}")

	for req in required_foremen:
		if req not in foreman_map:
			error_msg = f"CRITICAL BOOTSTRAP FAILED: Missing foreman '{req}'."
			logger.critical(error_msg)
			raise ImportError(error_msg)

	return foreman_map


class Dispatcher:
	def __init__(self, config):
		self.config = config
		self.filing_clerk = FilingClerk()
		self.active_threads = {}
		self.foreman_map = _build_foreman_map()

	def dispatch(self, sources):
		threads = []
		self.all_threads_done = threading.Event()

		for source in sources:
			source_config = SourceConfig(**source)
			thread = threading.Thread(target=self._dispatch_source, args=(source_config,))
			self.active_threads[source_config.source_name] = thread
			threads.append(thread)
			thread.start()

		def wait_for_all():
			for thread_loop in threads:
				thread_loop.join()
			self.all_threads_done.set()

		watcher = threading.Thread(target=wait_for_all)
		watcher.start()
		return self.all_threads_done

	def _dispatch_source(self, source_config: SourceConfig):
		source_name = source_config.source_name
		agent_type = source_config.agent_type

		if not all([source_name, agent_type]):
			logger.error(f"Source missing required config.")
			return

		try:
			# 1. AGENT HUNT
			agent_module = importlib.import_module(f"search_agents.{agent_type}_agent")
			credentials = None
			if agent_type == 'reddit':
				credentials = self.config.get_reddit_credentials()
			elif agent_type == 'gnews_io':
				credentials = self.config.get_gnews_io_credentials()

			raw_leads, bookmark = agent_module.hunt(source_config, credentials)

			if not raw_leads:
				# Even if no leads, update the 'last_checked_date' to show we looked
				db_manager.update_source_state(source_config.id, success=True)
				logger.info(f"Agent for '{source_name}' returned no new leads.")
				return

			# 2. FOREMAN TRANSLATION
			foreman_name = f"{agent_type}_foreman"
			foreman_handler = self.foreman_map.get(foreman_name)

			processed_leads = []
			if inspect.isclass(foreman_handler):
				foreman_instance = foreman_handler(source_config)
				processed_leads = foreman_instance.translate_leads(raw_leads)
			else:
				processed_leads = foreman_handler.translate(raw_leads, source_name)

			if not processed_leads:
				db_manager.update_source_state(source_config.id, success=True)
				return

			# 3. FILING
			self.filing_clerk.file_leads(processed_leads)

			# 4. COMMIT STATE (The Fix)
			# We pass the bookmark back to the DB so the NEXT hunt knows where to start.
			db_manager.update_source_state(source_config.id, success=True, new_bookmark=bookmark)
			logger.info(f"Source '{source_name}' state updated with bookmark: {bookmark}")

		except Exception as e:
			logger.critical(f"Error in dispatch loop for '{source_name}': {e}", exc_info=True)
			# Log the failure in the DB so the GUI shows the source is erroring
			db_manager.update_source_state(source_config.id, success=False)
		finally:
			if source_name in self.active_threads:
				del self.active_threads[source_name]