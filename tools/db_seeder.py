# ==========================================================
# Hunter's Command Console - Definitive DB Seeder
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import os
import sys

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import db_manager

def seed_database():
    """
    Populates the database with initial source domains and sources.
    This is now a two-phase process.
    """
    print("[SEEDER]: Populating database...")

    # --- Phase 1: Seed the Source Domains ---
    print(" -> Seeding source domains...")
    domains_to_add = [
        {'domain_name': 'reddit.com', 'agent_type': 'reddit', 'max_concurrent_requests': 2},
        {'domain_name': 'gnews.io', 'agent_type': 'gnews_io', 'max_concurrent_requests': 1},
        {'domain_name': 'testdata', 'agent_type': 'test_data', 'max_concurrent_requests': 1},
        {'domain_name': 'lorepodcast.com', 'agent_type': 'rss', 'max_concurrent_requests': 1},
        {'domain_name': 'unexplainedpodcast.com', 'agent_type': 'rss', 'max_concurrent_requests': 1}
    ]
    for domain in domains_to_add:
        db_manager.add_source_domain(domain)

    # --- Phase 2: Seed the Individual Sources ---
    print(" -> Seeding individual sources...")
    sources_to_add = [
        # Reddit Sources
        {'source_name': 'Reddit Paranormal', 'domain_name': 'reddit.com', 'target': 'paranormal', 'purpose': 'lead_generation'},
        {'source_name': 'Reddit Ghosts', 'domain_name': 'reddit.com', 'target': 'ghosts', 'purpose': 'lead_generation'},
        # GNews.io Sources
        {'source_name': 'GNews.io - Unexplained Phenomena', 'domain_name': 'gnews.io', 'target': '"unexplained phenomena"', 'purpose': 'lead_generation'},
        # Podcast Sources
        {'source_name': 'Lore Podcast', 'domain_name': 'lorepodcast.com', 'target': 'https://feeds.libsyn.com/65267/rss', 'purpose': 'training_material'},
        {'source_name': 'Unexplained Podcast', 'domain_name': 'unexplainedpodcast.com', 'target': 'https://unexplainedpodcast.com/episodes?format=rss', 'purpose': 'training_material'},
        # Test Source
        {'source_name': 'Test Data Source', 'domain_name': 'testdata', 'target': 'test_leads.json', 'purpose': 'lead_generation'}
    ]
    for source in sources_to_add:
        db_manager.add_source(source)

    print("[SEEDER]: Seeding complete.")

if __name__ == "__main__":
    seed_database()
