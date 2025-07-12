import os
import time
import re
import wikipedia
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import customtkinter as ctk

# --- FIX: Adding missing imports for the standalone script's main block ---
import threading
import queue
import config_manager

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")  # Classic terminal look

class DatasetGuardian(ctk.CTk):
    """
    A guardian application that monitors specific directories for new
    transcripts and ensures the dataset remains balanced.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Dataset Guardian")
        self.geometry("800x600")

        # --- GUI Setup ---
        self.log_font = ctk.CTkFont(size=14)
        self.log_textbox = ctk.CTkTextbox(self, font=self.log_font)
        self.log_textbox.pack(expand=True, fill="both", padx=20, pady=20)

# --- Configuration ---
CASE_DIRS = [
    "lore_transcripts",
    "g:\\My Drive\\Unexplained_Transcripts",
    # You can add more folders here later
]
NOT_CASE_DIR = "training_data/not_a_case"
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
]

# --- Setup ---
for directory in CASE_DIRS:
    os.makedirs(directory, exist_ok=True)
os.makedirs(NOT_CASE_DIR, exist_ok=True)

NEEDS_REBALANCE_CHECK = True


class TranscriptHandler(FileSystemEventHandler):
    """Watches for new files in ANY of the case directories."""

    def __init__(self, log_queue, rebalance_event):
        self.log_queue = log_queue
        self.rebalance_event = rebalance_event

    def on_created(self, event):
        global NEEDS_REBALANCE_CHECK
        if not event.is_directory and event.src_path.endswith(".txt"):
            NEEDS_REBALANCE_CHECK = True


def count_words_in_directories(list_of_dirs):
    """
    Calculates the grand total word count from a list of directories.
    """
    grand_total_words = 0
    for directory_path in list_of_dirs:
        if not os.path.exists(directory_path):
            print(f"Warning: Directory not found - {directory_path}")
            continue

        dir_total = 0
        for filename in os.listdir(directory_path):
            if filename.endswith(".txt"):
                filepath = os.path.join(directory_path, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        dir_total += len(f.read().split())
                except Exception as e:
                    print(f"[ERROR]: Could not read {filename}: {e}")

        print(f"  - Word count for '{directory_path}': {dir_total:,}")
        grand_total_words += dir_total

    return grand_total_words


def get_clean_wikipedia_article():
    """Fetches a random, verified clean Wikipedia article."""
    while True:
        try:
            random_title = wikipedia.random(pages=1)
            page = wikipedia.page(random_title, auto_suggest=False, redirect=True)
            content = page.content

            lower_content = content.lower()
            if any(keyword in lower_content for keyword in CONTAMINATION_KEYWORDS):
                time.sleep(1)
                continue

            return page.title, content

        except Exception:
            time.sleep(5)
            continue


def sanitize_filename(name):
    """Creates a safe filename."""
    clean_name = re.sub(r"[^\w\s-]", "", name)
    return clean_name.replace(" ", "_").lower()[:100]


def run_balance_check():
    """The core logic to check and fix the dataset balance."""
    global NEEDS_REBALANCE_CHECK

    print("\n[GUARDIAN ACTION]: Running balance check...")
    case_words = count_words_in_directories(CASE_DIRS)

    # --- FIX: Call the correct function and pass the directory as a list ---
    not_case_words = count_words_in_directories([NOT_CASE_DIR])

    print(
        f"[GUARDIAN REPORT]: Total 'case' words: {case_words:,} | 'not_a_case' words: {not_case_words:,}"
    )

    target_word_count = case_words * BALANCE_THRESHOLD

    while not_case_words < target_word_count:
        print(
            f"[GUARDIAN ACTION]: Balance is off. Hunting for new 'not_a_case' material..."
        )
        title, content = get_clean_wikipedia_article()

        if title and content:
            filename = f"wiki_{sanitize_filename(title)}.txt"
            filepath = os.path.join(NOT_CASE_DIR, filename)

            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                article_word_count = len(content.split())
                not_case_words += article_word_count
                print(
                    f"  -> Acquired '{title}' ({article_word_count:,} words). New total: {not_case_words:,}"
                )
            except Exception as e:
                print(f"  - Could not save file {filename}: {e}")
        time.sleep(2)

    print("[GUARDIAN STATUS]: Dataset is balanced. Returning to watch mode.")
    NEEDS_REBALANCE_CHECK = False


if __name__ == "__main__":
    try:
        import watchdog
        import wikipedia
    except ImportError:
        print("ERROR: Missing required libraries. Run: pip install watchdog wikipedia")
        exit()

    # The main block for running this script standalone
    event_handler = TranscriptHandler(queue.Queue(), threading.Event())
    observer = Observer()
    for path in CASE_DIRS:
        if os.path.exists(path):
            observer.schedule(event_handler, path, recursive=False)
            print(
                f"--- Dataset Guardian is now watching: '{os.path.abspath(path)}' ---"
            )

    observer.start()
    print("(Press Ctrl+C to stop the guardian)")

    try:
        run_balance_check()  # Run an initial check
        while True:
            time.sleep(10)
            if NEEDS_REBALANCE_CHECK:
                run_balance_check()

    except KeyboardInterrupt:
        observer.stop()
        print("\n--- Guardian has been deactivated. ---")

    observer.join()
