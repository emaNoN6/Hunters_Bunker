#  ==========================================================
#  Hunter's Command Console
#  #
#  File: data_guardian_gui.py
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

import customtkinter as ctk
import threading
import queue
import os
import time
import re
import wikipedia
import config_manager

# --- Configuration (can be adjusted here) ---
CASE_DIRS = ["g:\\My Drive\\training_data\\lore_transcripts", "g:\\My Drive\\training_data\\Unexplained_Transcripts"]
NOT_CASE_DIR = "g:\\My Drive\\training_data\\not_a_case"
BALANCE_THRESHOLD = float(config_manager.get_config_value("General", "balance_threshold") or 0.97)
CONTAMINATION_KEYWORDS = [
    "ghost",
    "haunted",
    "haunting",
    "supernatural",
    "paranormal",
    "spirit",
    "demon",
    "devil",
    "angel",
    "miracle",
    "apparition",
    "cryptozoology",
    "cryptid",
    "monster",
    "myth",
    "legend",
    "folklore",
    "ufo",
    "alien",
    "extraterrestrial",
    "witch",
    "witchcraft",
    "vampire",
    "werewolf",
    "zombie",
    "magic",
    "occult",
    "omen",
]


# ==============================================================================
# This is the "backend" logic. It's just a function that will run in a thread.
# It doesn't know anything about the GUI. It just takes a queue and an event.
# ==============================================================================
def guardian_worker(update_queue, stop_event, force_check_event):
    """The background daemon that does all the real work."""

    def log(message):
        """Helper to send updates to the GUI via the queue."""
        update_queue.put({"type": "log", "data": message})

    def update_stats(case_count, not_case_count):
        """Helper to send statistics to the GUI."""
        update_queue.put(
            {"type": "stats", "data": {"case": case_count, "not_case": not_case_count}}
        )

    def count_words(dirs):
        """Counts words in a list of directories."""
        total = 0
        for d in dirs:
            if not os.path.exists(d):
                continue
            for fname in os.listdir(d):
                if fname.endswith(".txt"):
                    try:
                        with open(os.path.join(d, fname), "r", encoding="utf-8") as f:
                            total += len(f.read().split())
                    except Exception:
                        pass
        return total

    # --- The Main Loop of the Daemon ---
    log("Guardian Activated. Initializing...")
    while not stop_event.is_set():
        # Check if we need to run a balance check
        if force_check_event.is_set():
            force_check_event.clear()  # Reset the event
            log("Balance check forced by user...")

            case_words = count_words([d for d in CASE_DIRS if os.path.exists(d)])
            not_case_words = count_words([NOT_CASE_DIR])
            update_stats(case_words, not_case_words)

            target_word_count = case_words * BALANCE_THRESHOLD

            while not_case_words < target_word_count and not stop_event.is_set():
                log("Balance off. Hunting for material...")
                try:
                    title = wikipedia.random(pages=1)
                    page = wikipedia.page(title, auto_suggest=False, redirect=True)
                    content = page.content
                    if not any(kw in content.lower() for kw in CONTAMINATION_KEYWORDS):
                        log(f"-> Acquired '{title}'...")
                        safe_title = (
                            re.sub(r"[^\w\s-]", "", title)
                            .replace(" ", "_")
                            .lower()[:100]
                        )
                        filepath = os.path.join(NOT_CASE_DIR, f"wiki_{safe_title}.txt")
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(content)
                        word_count = len(content.split())
                        not_case_words += word_count
                        update_stats(
                            case_words, not_case_words
                        )  # Update GUI with new count
                    else:
                        log(f"-> Contaminated: '{title}'. Discarding.")
                except Exception as e:
                    log(f"-> Wikipedia Error: {e}")
                time.sleep(2)  # Be polite

            log("Balance check complete. Watching...")

        # Wait for 5 seconds before checking again
        time.sleep(5)

    log("Guardian Deactivated.")


# ==============================================================================
# This is the GUI Class. It's only job is to display information
# and send signals to the backend worker.
# ==============================================================================
class GuardianApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dataset Guardian Console")
        self.geometry("600x400")

        # --- GUI State Variables ---
        # Using CTk's special StringVars makes updating labels easy.
        self.case_words_var = ctk.StringVar(value="Case Words: N/A")
        self.not_case_words_var = ctk.StringVar(value="Not-a-Case Words: N/A")
        self.balance_var = ctk.StringVar(value="Balance: N/A")
        self.balance_threshold = ctk.StringVar(value=f" / {BALANCE_THRESHOLD * 100:.0f}%")  
        self.status_var = ctk.StringVar(value="Status: Inactive")

        # --- Threading Control ---
        self.update_queue = queue.Queue()
        self.worker_thread = None
        self.stop_event = threading.Event()
        self.force_check_event = threading.Event()

        # --- Create Widgets ---
        ctk.CTkLabel(self, textvariable=self.case_words_var, font=("System", 15)).pack(
            pady=5
        )
        ctk.CTkLabel(
            self, textvariable=self.not_case_words_var, font=("System", 15)
        ).pack(pady=5)
        balance_frame = ctk.CTkFrame(self)
        balance_frame.pack(pady=10)
        ctk.CTkLabel(
            balance_frame, textvariable=self.balance_var, font=("System", 15, "bold")
        ).pack(pady=5, side="left", fill="none")
        ctk.CTkLabel(
            balance_frame, textvariable=self.balance_threshold, font=("System", 15, "bold")).pack(
                pady=5, side="left")
        ctk.CTkLabel(self, textvariable=self.status_var, font=("System", 14)).pack(
            pady=10
        )

        self.force_button = ctk.CTkButton(
            self,
            text="Force Rebalance Check",
            command=self.force_check,
            state="disabled",
        )
        self.force_button.pack(pady=10)

        # --- Start/Stop Button ---
        self.toggle_button = ctk.CTkButton(
            self, text="Activate Guardian", fg_color="green", command=self.toggle_worker
        )
        self.toggle_button.pack(pady=10)

        # Start the queue listener
        self.process_queue()

    def toggle_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            # Stop the worker
            self.status_var.set("Status: Deactivating...")
            self.stop_event.set()
            self.toggle_button.configure(state="disabled")
            self.force_button.configure(state="disabled")
        else:
            # Start the worker
            self.stop_event.clear()
            self.force_check_event.set()  # Trigger an initial check
            self.worker_thread = threading.Thread(
                target=guardian_worker,
                args=(self.update_queue, self.stop_event, self.force_check_event),
                daemon=True,
            )
            self.worker_thread.start()
            self.toggle_button.configure(text="Deactivate Guardian", fg_color="red")
            self.force_button.configure(state="normal")

    def force_check(self):
        self.status_var.set("Status: Forcing rebalance check...")
        self.force_check_event.set()

    def process_queue(self):
        """Checks for messages from the background thread and updates the GUI."""
        try:
            while True:
                message = self.update_queue.get_nowait()
                if message["type"] == "log":
                    self.status_var.set(f"Status: {message['data']}")
                elif message["type"] == "stats":
                    case_w = message["data"]["case"]
                    not_case_w = message["data"]["not_case"]
                    self.case_words_var.set(f"Case Words: {case_w:,}")
                    self.not_case_words_var.set(f"Not-a-Case Words: {not_case_w:,}")
                    balance_pct = (not_case_w / case_w * 100) if case_w > 0 else 100
                    self.balance_var.set(f"Balance: {balance_pct:.0f}%")
        except queue.Empty:
            pass

        # Keep listening
        self.after(100, self.process_queue)


if __name__ == "__main__":
    app = GuardianApp()
    app.mainloop()
