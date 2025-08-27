# ==========================================================
# Hunter's Command Console - Dispatcher Test Script
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import queue
import time

# --- Centralized Pathing ---
# This single import now handles all the path setup automatically.
from hunter.utils import path_utils
# --- End Pathing ---

from hunter import dispatcher
from hunter.utils.log_consumer import start_console_log_consumer


def run_test_hunt():
	"""
	Initializes a log queue and runs the main dispatcher hunt.
	"""
	print("--- Starting Dispatcher Test Hunt ---")

	log_queue = queue.Queue()
	start_console_log_consumer(log_queue)

	# Call the main dispatcher function
	dispatcher.run_hunt(log_queue)

	# Give the logger a moment to print the final messages
	time.sleep(1)

	print("--- Dispatcher Test Hunt Complete ---")


if __name__ == "__main__":
	run_test_hunt()
