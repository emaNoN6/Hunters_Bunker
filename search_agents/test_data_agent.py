# FILE: search_agents/test_data_agent.py (CORRECTED)
# ===================================================
# This version uses the final, standardized function signature to
# correctly receive and use the results_queue.

import json
import os


def hunt(target_info, credentials, log_queue, results_queue):
    """
    Reads a JSON file containing simulated leads and puts them into the queue
    for the GUI to process.
    """
    # Get the filename from the mission briefing, e.g., "test_leads.json"
    target_file = target_info.get("target")

    # Helper function for logging
    def log(message):
        log_queue.put(f"[TEST AGENT]: {message}")

    log(f"Deploying to firing range. Target: '{target_file}'")

    # Critical check: Make sure we have an evidence bag to put things in
    if results_queue is None:
        log("ERROR: No results_queue provided. Cannot return leads.")
        return

    if not os.path.exists(target_file):
        log(f"ERROR: Target file '{target_file}' not found.")
        return

    try:
        with open(target_file, "r") as f:
            leads = json.load(f)

        log(f"Successfully loaded {len(leads)} known targets.")

        # --- THE FIX ---
        # Put each lead (which is a dictionary) into the results queue.
        # This is the step that was missing.
        for lead in leads:
            results_queue.put(lead)

    except Exception as e:
        log(f"ERROR: Could not read or parse JSON file: {e}")
