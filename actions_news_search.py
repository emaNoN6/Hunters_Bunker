# The dispatcher is now much simpler. It gives every agent the same briefing.

import yaml
import threading
import queue
from search_agents import gnews_agent, reddit_agent  # Import agents
import config_manager

# A mapping from the 'type' in our YAML file to the actual agent function
AGENT_DISPATCH_TABLE = {
    "gnews": gnews_agent.hunt,
    "reddit": reddit_agent.hunt,
    # 'test': test_data_agent.hunt # We'll add this back later
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

    # Gather all credentials into one bundle to pass to every agent
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
            # Every agent gets the same standard arguments. This is our clean interface.
            thread = threading.Thread(
                target=agent_function,
                args=(target_info, credentials, log_queue, results_queue),
                daemon=True,
            )
            threads.append(thread)
            thread.start()
        else:
            log_queue.put(f"  -> Unknown target type '{target_type}'. Skipping.")

    # Wait for all agent threads to complete their mission
    for thread in threads:
        thread.join()

    log_queue.put("\n--- All agents have reported in. Intelligence sweep complete. ---")
    # Signal that the work is done by putting a special object in the queue
    if results_queue:
        results_queue.put("SEARCH_COMPLETE")
