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

# This file makes the 'hunter' package directly runnable.
# When you run `python -m hunter`, this is the code that executes.

from .hunter_app import HunterApp

def main():
    """The main entry point for the application."""
    print("Launching Hunter's Command Console...")
    app = HunterApp()
    app.mainloop()

if __name__ == "__main__":
    main()
