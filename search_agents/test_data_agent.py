# search_agents/test_data_agent.py

import json
import os


def hunt(log_queue):
    """
    A simple test agent that reads leads from a local JSON file.
    """
    log_queue.put("[TEST AGENT]: Waking up. Reading local test file...")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "test_leads.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log_queue.put(f"[TEST AGENT]: Found {len(data)} leads in test file.")
        return data
    except FileNotFoundError:
        log_queue.put("[TEST AGENT ERROR]: test_leads.json not found.")
        return []
    except Exception as e:
        log_queue.put(f"[TEST AGENT ERROR]: Failed to read test file: {e}")
        return []
