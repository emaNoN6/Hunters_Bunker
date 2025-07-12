# This is our refactored guardian. It's now a class-based "agent"
# that can be controlled by our main GUI. It communicates its status
# back to the GUI via a queue instead of printing to the console.

import os
import time
import re
import wikipedia
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class TranscriptHandler(FileSystemEventHandler):
    """A helper class for the watchdog observer."""

    def __init__(self, log_queue, rebalance_event):
        self.log_queue = log_queue
        self.rebalance_event = rebalance_event

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith(".txt"):
            self.log_queue.put(
                f"[GUARDIAN DETECTED]: New file: {os.path.basename(event.src_path)}"
            )
            self.rebalance_event.set()  # Signal that a check is needed


class DatasetGuardianAgent:
    def __init__(self, log_queue, stop_event):
        self.log_queue = log_queue
        self.stop_event = stop_event  # An event to signal when to stop
        self.rebalance_event = threading.Event()

        # Configuration
        self.case_dir = "lore_transcripts"
        self.not_case_dir = "training_data/not_a_case"
        self.balance_threshold = 0.95
        self.contamination_keywords = [
            "ghost",
            "haunted",
            "haunting",
            "supernatural",
            "paranormal",
            "spirit",
            "demon",
            "devil",
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
        ]

    def log(self, message):
        """Puts a message into the queue for the GUI to display."""
        self.log_queue.put(message)

    def count_words(self, directory_path):
        """Calculates total words in a directory."""
        total = 0
        if not os.path.exists(directory_path):
            return 0
        for fname in os.listdir(directory_path):
            if fname.endswith(".txt"):
                try:
                    with open(
                        os.path.join(directory_path, fname), "r", encoding="utf-8"
                    ) as f:
                        total += len(f.read().split())
                except Exception:
                    pass
        return total

    def get_clean_article(self):
        """Fetches a clean Wikipedia article."""
        while not self.stop_event.is_set():
            try:
                title = wikipedia.random(pages=1)
                self.log(f"  - Candidate found: '{title}'")
                page = wikipedia.page(title, auto_suggest=False, redirect=True)
                content = page.content.lower()
                if any(kw in content for kw in self.contamination_keywords):
                    self.log("    -> CONTAMINATED. Discarding.")
                    time.sleep(1)
                    continue
                self.log("    -> Sample is clean. Acquiring.")
                return page.title, page.content
            except Exception as e:
                self.log(f"    - Wikipedia error: {e}. Trying again.")
                time.sleep(5)

    def run_balance_check(self):
        """The main balancing logic."""
        self.log("\n[GUARDIAN ACTION]: Running balance check...")
        case_words = self.count_words(self.case_dir)
        not_case_words = self.count_words(self.not_case_dir)
        self.log(
            f"[GUARDIAN REPORT]: 'case' words: {case_words:,} | 'not_a_case' words: {not_case_words:,}"
        )

        target_word_count = case_words * self.balance_threshold

        while not_case_words < target_word_count and not self.stop_event.is_set():
            self.log("[GUARDIAN ACTION]: Balance off. Hunting for material...")
            title, content = self.get_clean_article()
            if title and content:
                safe_title = (
                    re.sub(r"[^\w\s-]", "", title).replace(" ", "_").lower()[:100]
                )
                filepath = os.path.join(self.not_case_dir, f"wiki_{safe_title}.txt")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                word_count = len(content.split())
                not_case_words += word_count
                self.log(
                    f"  -> Acquired '{title}' ({word_count:,} words). New total: {not_case_words:,}"
                )
            time.sleep(2)

        self.log("[GUARDIAN STATUS]: Dataset is balanced.")

    def run(self):
        """The main entry point for the thread. This is the daemon's main loop."""
        self.log("--- Dataset Guardian is now active. ---")

        # Setup and start watchdog
        handler = TranscriptHandler(self.log_queue, self.rebalance_event)
        observer = Observer()
        observer.schedule(handler, self.case_dir, recursive=False)
        observer.start()

        # Run an initial check
        self.rebalance_event.set()

        while not self.stop_event.is_set():
            # The wait() method is efficient. It sleeps until the event is set.
            # We add a timeout so it can periodically check the main stop_event.
            self.rebalance_event.wait(timeout=5.0)

            if self.rebalance_event.is_set():
                self.run_balance_check()
                self.rebalance_event.clear()  # Reset the event after handling it

        # Cleanup
        observer.stop()
        observer.join()
        self.log("--- Dataset Guardian has been deactivated. ---")
