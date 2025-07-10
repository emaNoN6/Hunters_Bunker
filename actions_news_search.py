# actions_news_search.py

import db_manager
from search_agents import test_data_agent

# We will import our other agents here later, like:
# from search_agents import reddit_agent
# from search_agents import gnews_agent

# This dictionary maps the 'source_type' from our database
# to the actual agent module that knows how to handle it.
AGENT_DISPATCH_TABLE = {
    "test_data": test_data_agent,
    # "reddit": reddit_agent,
    # "gnews": gnews_agent
}


def search_all_sources(log_queue):
    """
    The main dispatcher function. It gets the list of active sources
    from the database and calls the appropriate agent for each one.
    """
    log_queue.put("[DISPATCHER]: Beginning search operation.")

    # For now, we'll use a hardcoded list for testing.
    # Later, this will come from db_manager.get_active_sources()
    # active_sources = db_manager.get_active_sources()
    active_sources = [{"source_name": "Test Data Source", "source_type": "test_data"}]

    all_results = []

    if not active_sources:
        log_queue.put("[DISPATCHER]: No active sources found in database.")
        return []

    for source in active_sources:
        source_type = source.get("source_type")
        agent_module = AGENT_DISPATCH_TABLE.get(source_type)

        if agent_module:
            log_queue.put(
                f"[DISPATCHER]: Dispatching '{source.get('source_name')}' agent..."
            )
            try:
                # We call the 'hunt' function for the matched agent
                results = agent_module.hunt(log_queue)
                if results:
                    all_results.extend(results)
            except Exception as e:
                log_queue.put(
                    f"[DISPATCHER ERROR]: Agent '{source.get('source_name')}' failed: {e}"
                )
        else:
            log_queue.put(
                f"[DISPATCHER WARNING]: No agent found for source type '{source_type}'."
            )

    log_queue.put(
        f"[DISPATCHER]: Search complete. Found {len(all_results)} total leads."
    )
    return all_results
