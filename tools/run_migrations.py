#  ==========================================================
#  Hunter's Command Console
#  #
#  File: run_migrations.py
#  Last Modified: 7/29/25, 6:48 PM
#  #
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
# ==========================================================
# Hunter's Command Console - Migration Runner
# This is the standalone script that an administrator (you)
# runs to apply database schema updates. It calls the secure
# migration manager library.
# ==========================================================

import os
import sys

# --- Pathing Magic ---
# This tells the script to look one directory up (to the main project root)
# so it can find our 'hunter' package.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

# Import the migration manager from our new, secure admin package
from hunter.admin import migration_manager

# --- The Warding Circle ---
# This ensures the code only runs when you execute this script directly.
if __name__ == "__main__":
	print("--- Hunter's Almanac Migration Tool ---")
	print("This tool will connect as the admin user and apply any necessary schema updates.")

	# Cast the spell
	migration_manager.run_migrations()

	print("\n--- Migration process complete. ---")

