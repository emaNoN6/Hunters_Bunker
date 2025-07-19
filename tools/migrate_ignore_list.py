# tools/migrate_ignore_list.py

import os
import sys
import yaml
import re
import feedparser
import requests

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager

IGNORE_FILE = os.path.join(project_root, "ignore_list.yaml")


def migrate_ignores():
    """
    Reads the old ignore_list.yaml and populates the acquisition_log table.
    """
    print("[MIGRATOR]: Migrating rules from ignore_list.yaml to database...")

    if not os.path.exists(IGNORE_FILE):
        print("[MIGRATOR]: ignore_list.yaml not found. Nothing to migrate.")
        return

    with open(IGNORE_FILE, "r") as f:
        ignore_rules = yaml.safe_load(f)

    all_sources = db_manager.get_all_sources()  # Another new function for db_manager
    source_map = {s["source_name"]: s for s in all_sources}

    for source_name, rules in ignore_rules.items():
        if source_name not in source_map:
            print(
                f" -> WARNING: Source '{source_name}' from YAML not found in database. Skipping."
            )
            continue

        source_info = source_map[source_name]
        source_id = source_info["id"]
        source_type = source_info["source_type"]
        target = source_info["target"]
        ignore_keywords = rules.get("ignore_keywords", [])

        print(f" -> Processing ignore rules for '{source_name}'...")

        try:
            episodes = []
            if source_type == "rss":
                feed = feedparser.parse(target)
                episodes = feed.entries
            elif source_type == "pocketcasts_json":
                response = requests.get(target)
                data = response.json()
                episodes = data.get("podcast", {}).get("episodes", [])

            ignored_count = 0
            for episode in episodes:
                title = episode.get("title", "")
                for keyword in ignore_keywords:
                    if re.search(keyword, title, re.IGNORECASE):
                        item_url = (
                            episode.get("id")
                            if source_type == "rss"
                            else episode.get("url")
                        )
                        if item_url:
                            db_manager.log_acquisition(
                                item_url,
                                source_id,
                                title,
                                "IGNORED",
                                f"Matched keyword: {keyword}",
                            )
                            ignored_count += 1
                        break  # Move to the next episode

            print(f"   -> Logged {ignored_count} episodes as IGNORED for this source.")

        except Exception as e:
            print(f"   -> ERROR processing source '{source_name}': {e}")

    print("[MIGRATOR]: Migration complete. You can now safely delete ignore_list.yaml.")


if __name__ == "__main__":
    # This also requires new functions in db_manager.py
    print("NOTE: This script requires new functions in db_manager.py to run.")
    # migrate_ignores()
