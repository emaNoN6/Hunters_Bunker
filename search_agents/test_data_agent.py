# FILE 2: search_agents/test_data_agent.py (NEW FILE)
# ===================================================
# The Test Data Specialist. Its only job is to read our controlled data file.
# Create this file inside your 'search_agents' folder.

import json
import os


def hunt(target_info, credentials, log_queue, results_queue):
    """
    Reads a JSON file containing simulated leads and returns them.
    """
    target_file = target_info.get("target")  # e.g., "test_leads.json"

    def log(message):
        log_queue.put(f"[TEST AGENT]: {message}")

    log(f"Deploying to firing range. Target: '{target_file}'")

    if not os.path.exists(target_file):
        log(f"ERROR: Target file '{target_file}' not found.")
        return

    try:
        with open(target_file, "r") as f:
            leads = json.load(f)

        log(f"Successfully loaded {len(leads)} known targets.")
        for lead in leads:
            results_queue.put(lead)  # Put each lead into the results queue

    except Exception as e:
        log(f"ERROR: Could not read or parse JSON file: {e}")
