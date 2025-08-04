# hunter/actions_news_search.py

from . import db_manager
from . import config_manager
from search_agents import test_data_agent, gnews_io_agent, reddit_agent

AGENT_DISPATCH_TABLE = {
	"test_data": test_data_agent,
	"gnews_io":  gnews_io_agent,
	"reddit":    reddit_agent
}


def search_all_sources(log_queue):
	"""
    The main dispatcher function. Now handles API key retrieval and
    acquisition log checking.
    """
	log_queue.put("[DISPATCHER]: Beginning search operation.")

	active_sources = db_manager.get_active_lead_sources()
	all_results = []

	if not active_sources:
		log_queue.put("[DISPATCHER]: No active lead generation sources found.")
		return []

	log_queue.put(f"[DISPATCHER]: Found {len(active_sources)} active source(s).")

	# --- Pre-load API keys once at the start of the hunt ---
	gnews_creds = config_manager.get_gnews_io_credentials()
	reddit_creds = config_manager.get_reddit_credentials()

	for source in active_sources:
		agent_type = source.get("agent_type")
		agent_module = AGENT_DISPATCH_TABLE.get(agent_type)

		if agent_module:
			log_queue.put(f"[DISPATCHER]: Dispatching '{source.get('source_name')}' agent...")
			try:
				# Pass the specific credentials the agent needs.
				if agent_type == 'gnews_io':
					results = agent_module.hunt(log_queue, source, gnews_creds)
				elif agent_type == 'reddit':
					results = agent_module.hunt(log_queue, source, reddit_creds)
				else:  # For agents that don't need keys
					results = agent_module.hunt(log_queue, source)

				# The dispatcher is now responsible for logging
				if results:
					new_leads = []
					for lead in results:
						if not db_manager.check_acquisition_log(lead['url']):
							new_leads.append(lead)
							db_manager.log_acquisition(lead['url'], source['id'], lead['title'], 'PROCESSED')
						else:
							log_queue.put(f"[DISPATCHER]: Discarding old lead: {lead['title']}")
					all_results.extend(new_leads)

				db_manager.update_source_check_time(source['id'])
			except Exception as e:
				log_queue.put(f"[DISPATCHER ERROR]: Agent '{source.get('source_name')}' failed: {e}")
		else:
			log_queue.put(f"[DISPATCHER WARNING]: No agent found for agent type '{agent_type}'.")

	log_queue.put(f"[DISPATCHER]: Search complete. Found {len(all_results)} new leads.")
	return all_results
