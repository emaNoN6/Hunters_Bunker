# FILE 3: actions_news_search.py (SAFELY UPDATED)
# ===============================================
# We are adding the new test_data_agent to the dispatcher's capabilities.

import yaml
import threading
import queue

# --- NEW: Import the test data agent ---
from search_agents import gnews_agent, reddit_agent, test_data_agent
import config_manager

# --- NEW: Add the test agent to the dispatch table ---
AGENT_DISPATCH_TABLE = {
    "gnews": gnews_agent.hunt,
    "reddit": reddit_agent.hunt,
    "test": test_data_agent.hunt,  # Our new agent is now recognized
}


def run_all_searches(log_queue, results_queue):
    """
    Loads the master plan and dispatches all agents in separate threads.
    """
    log_queue.put("--- Loading search targets from search_targets.yaml ---")
    try:
        with open("search_targets.yaml", "r") as f:
            targets = yaml.safe_load(f)
    except FileNotFoundError:
        log_queue.put("ERROR: search_targets.yaml not found. Aborting mission.")
        results_queue.put("SEARCH_COMPLETE")
        return

    credentials = {
        "gnews_api_key": config_manager.get_gnews_api_key(),
        "reddit_creds": config_manager.get_reddit_credentials(),
    }

    threads = []
    log_queue.put("--- Beginning intelligence sweep ---")

    for target_info in targets:
        target_type = target_info.get("type")
        agent_function = AGENT_DISPATCH_TABLE.get(target_type)

        if agent_function:
            thread = threading.Thread(
                target=agent_function,
                args=(target_info, credentials, log_queue, results_queue),
                daemon=True,
            )
            threads.append(thread)
            thread.start()
        else:
            log_queue.put(f"  -> Unknown target type '{target_type}'. Skipping.")

    for thread in threads:
        thread.join()

    log_queue.put("\n--- All agents have reported in. Intelligence sweep complete. ---")
    results_queue.put("SEARCH_COMPLETE")
