import json
import os


def hunt(target_info, credentials, log_queue, results_queue):
    """
    Reads a JSON file and uses the provided queues to report back.
    """
    target_file = target_info.get("target")

    log_queue.put(f"[TEST AGENT]: Deploying to firing range. Target: '{target_file}'")

    if not os.path.exists(target_file):
        log_queue.put(f"  - TEST ERROR: Target file '{target_file}' not found.")
        return

    try:
        with open(target_file, "r") as f:
            leads = json.load(f)

        log_queue.put(
            f"  - TEST AGENT: Successfully loaded {len(leads)} known targets."
        )
        for lead in leads:
            results_queue.put(lead)

    except Exception as e:
        log_queue.put(f"  - TEST ERROR: Could not read or parse JSON file: {e}")
