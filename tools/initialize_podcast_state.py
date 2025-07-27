#  ==========================================================
#  Hunter's Command Console
#  #
#  File: initialize_podcast_state.py
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

import os
import sys
import feedparser
import requests
from datetime import datetime
import dateutil.parser

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager

def get_latest_episode_from_feed(source):
    """
    Parses a podcast feed and returns the URL/GUID of the newest episode.
    """
    source_type = source.get('source_type')
    target = source.get('target')
    latest_episode = None
    latest_date = None

    print(f" -> Parsing feed for '{source.get('source_name')}'...")
    
    try:
        if source_type == 'rss':
            feed = feedparser.parse(target)
            if not feed.entries: return None
            
            for entry in feed.entries:
                pub_date = dateutil.parser.parse(entry.published)
                if latest_date is None or pub_date > latest_date:
                    latest_date = pub_date
                    latest_episode = entry.id # The GUID is in the 'id' field
        
        elif source_type == 'pocketcasts_json':
            response = requests.get(target)
            data = response.json()
            episodes = data.get('podcast', {}).get('episodes', [])
            if not episodes: return None

            for episode in episodes:
                pub_date = dateutil.parser.isoparse(episode['published'])
                if latest_date is None or pub_date > latest_date:
                    latest_date = pub_date
                    latest_episode = episode['url'] # The URL is our unique key here

        return latest_episode

    except Exception as e:
        print(f"    -> ERROR parsing feed: {e}")
        return None


def initialize_state():
    """
    Finds the latest episode for each podcast source and updates the database.
    """
    print("[INITIALIZER]: Setting initial state for podcast agents...")
    
    # We need a function in db_manager to get sources by type
    podcast_sources = db_manager.get_sources_by_type(['rss', 'pocketcasts_json'])
    
    if not podcast_sources:
        print("[INITIALIZER]: No podcast sources found in the database.")
        return

    for source in podcast_sources:
        source_id = source['id']
        source_name = source['source_name']
        
        latest_item_id = get_latest_episode_from_feed(source)
        
        if latest_item_id:
            print(f" -> Found latest episode for '{source_name}'. Updating database...")
            db_manager.update_source_last_item(source_id, latest_item_id)
        else:
            print(f" -> Could not determine latest episode for '{source_name}'.")

    print("[INITIALIZER]: State initialization complete.")

if __name__ == "__main__":
    # We'll need to add get_sources_by_type and update_source_last_item to db_manager.py
    # For now, this is the logic.
    print("NOTE: This script requires new functions in db_manager.py to run.")
    # initialize_state() 
