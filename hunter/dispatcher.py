# ==========================================================
# Hunter's Command Console - Dispatcher (v4.1 - State Fixed)
# ==========================================================

import importlib
import logging
import threading
import inspect
from pathlib import Path

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
		self.all_threads_done = None
		self.config = config
		self.filing_clerk = FilingClerk()
		self.active_threads = {}
		self.foreman_map = _build_foreman_map()

	def dispatch(self):
		"""Dispatch all active domains. Gets its own data."""
		domains = db_manager.get_domains_with_sources()

		if not domains:
			logger.info("No active domains/sources found.")
			return threading.Event()  # Already "done"

		threads = []
		self.all_threads_done = threading.Event()

		for domain_name, domain_info in domains.items():
			foreman_name = f"{domain_info['agent_type']}_foreman"
			if foreman_name not in self.foreman_map:
				logger.error(f"No foreman found for '{foreman_name}', skipping domain '{domain_name}'")
				continue

			thread = threading.Thread(
					target=self._dispatch_domain,
					args=(domain_name, domain_info),
					name=f"domain-{domain_name}"
			)
			self.active_threads[domain_name] = thread
			threads.append(thread)
			thread.start()

		def wait_for_all():
			for t in threads:
				t.join()
			self.all_threads_done.set()

		watcher = threading.Thread(target=wait_for_all)
		watcher.start()
		return self.all_threads_done

	def _dispatch_domain(self, domain_name, domain_info):
		"""Handle all sources for a single domain."""
		agent_type = domain_info['agent_type']
		sources = domain_info['sources']
		foreman_name = f"{agent_type}_foreman"
		foreman_handler = self.foreman_map[foreman_name]

		# Get credentials once per domain
		credentials = self._get_credentials(agent_type)

		# Import agent once per domain
		try:
			agent_module = importlib.import_module(f"search_agents.{agent_type}_agent")
		except ImportError as e:
			logger.critical(f"Failed to import agent for '{agent_type}': {e}")
			return

		# Process each source
		for source in sources:
			try:
				self._process_source(source, agent_module, foreman_handler, credentials)
			except Exception as e:
				logger.critical(f"Error processing source '{source.source_name}': {e}", exc_info=True)
				db_manager.update_source_state(source.id, success=False)

		logger.info(f"Domain '{domain_name}' complete. Processed {len(sources)} sources.")

	def _process_source(self, source, agent_module, foreman_handler, credentials):
		"""Process a single source - agent → foreman → filing."""
		# 1. Hunt
		raw_leads, bookmark = agent_module.hunt(source, credentials)

		if not raw_leads:
			db_manager.update_source_state(source.id, success=True)
			logger.info(f"Agent for '{source.source_name}' returned no new leads.")
			return

		# 2. Translate
		if inspect.isclass(foreman_handler):
			foreman_instance = foreman_handler(source)
			processed_leads = foreman_instance.translate_leads(raw_leads)
		else:
			processed_leads = foreman_handler.translate(raw_leads, source.source_name)

		if not processed_leads:
			db_manager.update_source_state(source.id, success=True)
			return

		# 3. File
		self.filing_clerk.file_leads(processed_leads)

		# 4. Update state
		db_manager.update_source_state(source.id, success=True, new_bookmark=bookmark)
		logger.info(f"Source '{source.source_name}' done. Bookmark: {bookmark}")

	def _get_credentials(self, agent_type):
		match agent_type:
			case 'reddit':
				return self.config.get_reddit_credentials()
			case 'gnews_io':
				return self.config.get_gnews_io_credentials()
			case _:
				return None
