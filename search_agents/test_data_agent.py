#  ==========================================================
#  Hunter's Command Console
#  #
#  File: test_data_agent.py
#  Last Modified: 7/27/25, 2:57 PM
#  Copyright (c) 2025, M. Stilson & Codex
#  #
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the MIT License.
#  #
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  LICENSE file for more details.
#  ==========================================================

# search_agents/test_data_agent.py

import json
import os


# The hunt function now accepts the 'source' dictionary as an argument
def hunt(log_queue, source):
    """
    A simple test agent that reads leads from a local JSON file.
    """
    log_queue.put("[TEST AGENT]: Waking up. Reading local test file...")

    # The target file is now defined in the database
    target_file = source.get("target", "test_leads.json")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, "data", target_file)
    print(f"[TEST AGENT]: Looking for test file at {json_path}")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        log_queue.put(f"[TEST AGENT]: Found {len(data)} leads in test file.")
        return data
    except FileNotFoundError:
        log_queue.put(f"[TEST AGENT ERROR]: {target_file} not found.")
        return []
    except Exception as e:
        log_queue.put(f"[TEST AGENT ERROR]: Failed to read test file: {e}")
        return []
