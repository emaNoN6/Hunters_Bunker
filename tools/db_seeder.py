# tools/db_seeder.py

import os
import sys

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager

# This script populates the 'sources' table with our initial hunting grounds.
# It's designed to be run once.


def seed_database():
    """Adds the initial set of sources to the database."""
    print("[SEEDER]: Populating database with initial sources...")

    sources_to_add = [
        # --- Podcast Agents ---
        {
            "source_name": "Lore Podcast",
            "source_type": "rss",
            "target": "https://feeds.libsyn.com/65267/rss",
            "purpose": "training_material",
        },
        {
            "source_name": "Unexplained Podcast",
            "source_type": "pocketcasts_json",
            "target": "https://podcasts.pocketcasts.com/f96fb8d0-a70d-0133-2dfa-6dc413d6d41d/episodes_full_1751585827.json",
            "purpose": "training_material",
        },
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
        # --- GNews.io Agents ---
        {
            "source_name": "GNews.io - Strange Disappearance",
            "source_type": "gnews_io",
            "target": '"strange disappearance"',
            "purpose": "lead_generation",
        },
        {
            "source_name": "GNews.io - Unexplained Phenomena",
            "source_type": "gnews_io",
            "target": '"unexplained phenomena"',
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


def seed_system_tasks():
    """Populates the system_tasks table with its initial set of known tasks."""
    print("[SEEDER]: Populating database with initial system tasks...")

    tasks_to_add = [
        {
            "task_name": "CHECK_MODEL_STALENESS",
            "status": "PENDING",
            "notes": "Checks if the AI model needs to be retrained.",
        },
        {
            "task_name": "RUN_DATA_BALANCER",
            "status": "PENDING",
            "notes": "Checks if the 'not_a_case' dataset is balanced against the case files.",
        },
        {
            "task_name": "ARCHIVE_OLD_LEADS",
            "status": "PENDING",
            "notes": "Future task to archive or delete very old, unreviewed leads from the acquisition_log.",
        },
    ]

    # We'll need a new function in db_manager to handle this
    for task in tasks_to_add:
        db_manager.add_system_task(task)

    print("[SEEDER]: System tasks seeding complete.")


if __name__ == "__main__":
    # The seeder now runs both functions
    seed_database()
    seed_system_tasks()
