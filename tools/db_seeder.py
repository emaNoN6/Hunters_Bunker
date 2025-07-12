# db_seeder.py

import os
import sys
from hunter import db_manager

# --- Pathing Magic ---
# This tells the script to look one directory up (to the main project root)
# so it can find our 'hunter' package.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---


# This script populates the 'sources' table with our initial hunting grounds.
# It's designed to be run once.


def seed_database():
    """Adds the initial set of sources to the database."""
    print("[SEEDER]: Populating database with initial sources...")

    sources_to_add = [
        # --- Reddit Agents ---
        {
            "source_name": "Reddit Paranormal",
            "source_type": "reddit",
            "target": "paranormal",  # The subreddit name
            "strategy": "newest_posts",
            "purpose": "lead_generation",
        },
        {
            "source_name": "Reddit Ghosts",
            "source_type": "reddit",
            "target": "ghosts",
            "strategy": "newest_posts",
            "purpose": "lead_generation",
        },
        {
            "source_name": "Reddit High Strangeness",
            "source_type": "reddit",
            "target": "HighStrangeness",
            "strategy": "newest_posts",
            "purpose": "lead_generation",
        },
        # --- GNews Agents ---
        {
            "source_name": "GNews - Strange Disappearance",
            "source_type": "gnews",
            "target": "strange disappearance",  # The search keyword
            "purpose": "lead_generation",
        },
        {
            "source_name": "GNews - Unexplained Phenomena",
            "source_type": "gnews",
            "target": "unexplained phenomena",
            "purpose": "lead_generation",
        },
        # --- Test Agent (for debugging) ---
        {
            "source_name": "Test Data Source",
            "source_type": "test_data",
            "target": "test_leads.json",
            "purpose": "lead_generation",
        },
    ]

    for source in sources_to_add:
        db_manager.add_source(source)

    print("[SEEDER]: Seeding complete.")


if __name__ == "__main__":
    seed_database()
