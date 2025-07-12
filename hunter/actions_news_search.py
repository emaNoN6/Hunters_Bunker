# actions_news_search.py

import db_manager
from search_agents import test_data_agent, gnews_agent, reddit_agent, gnews_io_agent

# This dictionary maps the 'source_type' from our database
# to the actual agent module that knows how to handle it.
AGENT_DISPATCH_TABLE = {
    "test_data": test_data_agent,
    "gnews": gnews_agent,
    "gnews_io": gnews_io_agent,
    "reddit": reddit_agent,
}


def search_all_sources(log_queue):
    """
    The main dispatcher function. It gets the list of active sources
    from the database and calls the appropriate agent for each one.
    """
    log_queue.put("[DISPATCHER]: Beginning search operation.")

    log_queue.put("[DISPATCHER]: Querying database for active sources...")
    active_sources = db_manager.get_active_lead_sources()

    all_results = []

    if not active_sources:
        log_queue.put(
            "[DISPATCHER]: No active lead generation sources found in database."
        )
        return []

    log_queue.put(f"[DISPATCHER]: Found {len(active_sources)} active source(s).")

    for source in active_sources:
        source_type = source.get("source_type")
        agent_module = AGENT_DISPATCH_TABLE.get(source_type)

        if agent_module:
            log_queue.put(
                f"[DISPATCHER]: Dispatching '{source.get('source_name')}' agent..."
            )
            try:
                # We now pass the full source dictionary to the agent
                results = agent_module.hunt(log_queue, source)

                # The agent itself now handles checking the acquisition log,
                # so we just extend the results.
                if results:
                    all_results.extend(results)

                # Update the source's last checked time
                db_manager.update_source_check_time(source["id"])

            except Exception as e:
                log_queue.put(
                    f"[DISPATCHER ERROR]: Agent '{source.get('source_name')}' failed: {e}"
                )
        else:
            log_queue.put(
                f"[DISPATCHER WARNING]: No agent found for source type '{source_type}'."
            )

    log_queue.put(f"[DISPATCHER]: Search complete. Found {len(all_results)} new leads.")
    return all_results
