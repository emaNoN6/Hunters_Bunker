#  ==========================================================
#  Hunter's Command Console
#  #
#  File: __main__.py
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

# hunter/__main__.py

# First, import our tools
from . import hunter_app
from . import db_manager


def main():
    """The main entry point for the application."""

    # --- THIS IS THE NEW, CORRECT LOCATION FOR THE PRE-FLIGHT CHECK ---
    print("--- Hunter's Command Console: Pre-Flight Check ---")

    # We need a simple function to check the DB version without the full GUI.
    # We'll add this to the db_manager.
    is_db_ok, message = db_manager.verify_db_version()

    if not is_db_ok:
        # If the check fails, we print the error to the console and exit.
        # The GUI is never even created.
        print(f"\n[FATAL STARTUP ERROR]: {message}")
        print("\n--- Pre-Flight Check FAILED. Aborting launch. ---")
        return  # Exit the program

    print(f"[SUCCESS]: {message}")
    print("\n--- Pre-Flight Check Complete. Launching Main Console... ---")

    # Only if the check passes do we launch the app.
    app = hunter_app.HunterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
