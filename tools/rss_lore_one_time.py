#  ==========================================================
#  Hunter's Command Console
#  #
#  File: rss_lore_one_time.py
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

# tools/migrate_lore_ignores.py

import os
import sys
import feedparser
import re

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager

LORE_FEED_URL = "https://feeds.libsyn.com/65267/rss"


def migrate_lore_ignores():
    """
    Scans the full Lore RSS feed with smarter filtering and logs only the
    true junk episodes to the acquisition_log with a status of 'IGNORED'.
    """
    print("[MIGRATOR]: Beginning Lore ignore list migration...")

    lore_source = db_manager.get_source_by_name("Lore Podcast")
    if not lore_source:
        print(
            "[MIGRATOR ERROR]: Could not find 'Lore Podcast' in the sources table. Aborting."
        )
        return

    lore_source_id = lore_source["id"]

    print(" -> Fetching full Lore RSS feed...")
    feed = feedparser.parse(LORE_FEED_URL)
    if feed.bozo:
        print(f" -> ERROR fetching feed: {feed.bozo_exception}")
        return

    print(f" -> Found {len(feed.entries)} total episodes. Applying filters...")

    ignored_count = 0
    for episode in feed.entries:
        main_title = episode.get("title", "").strip()
        episode_type = episode.get("itunes_episodetype", "unknown")

        ignore = False
        reason = ""

        # --- The New, More Robust Warding Circle ---
        # Rule 1: Ignore anything that isn't a 'full' episode.
        if episode_type != "full":
            ignore = True
            reason = f"Type is '{episode_type}'"

        # Rule 2: Ignore any title that contains our junk keywords.
        elif re.search(
            r"REMASTERED|INTRODUCING|DEEPER LORE", main_title, re.IGNORECASE
        ):
            ignore = True
            reason = "Matched junk keyword"

        # Rule 3: This is the key. We now check if a title is VALID.
        # A title is valid if it starts with "Lore ", "Legends ".
        # We also check for the old "Episode " format to be safe.
        is_valid_format = (
            main_title.lower().startswith("lore ")
            or main_title.lower().startswith("legends ")
            or main_title.lower().startswith("episode ")
        )

        # If it's not a bonus/junk keyword AND it's not a valid format, then it's junk.
        if not ignore and not is_valid_format:
            ignore = True
            reason = "Non-standard title format"
        # --- End New Logic ---

        if ignore:
            guid = episode.get("id")
            if guid:
                db_manager.log_acquisition(
                    guid, lore_source_id, main_title, "IGNORED", reason
                )
                ignored_count += 1
            else:
                print(
                    f" -> WARNING: Could not find GUID for ignored episode: {main_title}"
                )

    print(
        f"\n[MIGRATOR]: Migration complete. Logged {ignored_count} Lore episodes as IGNORED in the database."
    )


if __name__ == "__main__":
    migrate_lore_ignores()
