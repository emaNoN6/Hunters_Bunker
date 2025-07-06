# ==========================================================
# Hunter's Command Console - Dataset Balancer v11.0
# This version adds more robust filtering to avoid non-English
# bookshelves and to handle apostrophes in shelf names.
# ==========================================================

import os
import re
import random
import time
import config_manager
from gutenbergpy import textget
from gutenbergpy.gutenbergcache import GutenbergCache

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CASE_DIRECTORIES = [
    os.path.join(BASE_DIR, "lore_transcripts"),
    os.path.join(BASE_DIR, "Unexplained_Transcripts"),
    os.path.join(BASE_DIR, "training_data", "forteana"),
    os.path.join(BASE_DIR, "training_data", "demonic"),
    os.path.join(BASE_DIR, "training_data", "cryptids"),
]
NOT_CASE_DIR = os.path.join(BASE_DIR, "training_data", "not_a_case")
BALANCE_THRESHOLD = float(
    config_manager.get_config_value("General", "balance_threshold")
)

# --- Helper Functions ---


def initialize_gutenberg_cache():
    """
    The smart cache initialization ritual.
    It checks if the cache exists before trying to build it.
    """
    print("  -> Initializing Gutenberg catalog...")
    if GutenbergCache.exists():
        print("  -> Found existing Gutenberg cache. Loading...")
        try:
            cache = GutenbergCache.get_cache()
            print("  -> SUCCESS: Catalog initialized from existing cache.")
            return cache
        except Exception as e:
            print(f"[FATAL ERROR]: Failed to load existing Gutenberg cache: {e}")
            return None
    else:
        print(
            "  -> Cache not found. Performing one-time setup (this will take a long time)..."
        )
        try:
            GutenbergCache.create(refresh=False)
            cache = GutenbergCache.get_cache()
            print("  -> SUCCESS: Gutenberg cache created and populated.")
            return cache
        except Exception as e:
            print(f"[FATAL ERROR]: Failed to create Gutenberg cache: {e}")
            return None


def count_words_and_files(dir_list):
    """Counts the total words and files across a list of directories."""
    total_words = 0
    total_files = 0
    for directory in dir_list:
        if not os.path.isdir(directory):
            continue
        for filename in os.listdir(directory):
            if filename.endswith(".txt"):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        total_words += len(f.read().split())
                    total_files += 1
                except Exception as e:
                    print(f"[BALANCER WARNING]: Could not read {filepath}: {e}")
    return total_words, total_files


def get_average_case_size():
    """Calculates the average word count of our existing case files."""
    case_words, case_files = count_words_and_files(CASE_DIRECTORIES)
    if case_files == 0:
        return 4000
    return case_words // case_files


def get_boring_book(cache, processed_in_session, boring_shelves):
    """Finds and downloads the plain text of a random non-fiction book."""
    if not boring_shelves:
        print("[BALANCER WARNING]: The list of boring bookshelves is empty.")
        return None, None

    try:
        shelf = random.choice(boring_shelves)
        print(f"  -> Hunting for a book on the thrilling bookshelf of: '{shelf}'")

        # --- FIX for Apostrophe Demon ---
        # We escape the single quote for the SQL query.
        safe_shelf_name = shelf.replace("'", "''")

        book_ids = cache.query(
            bookshelves=[safe_shelf_name],
            languages=["en"],
            downloadtype=[
                "text/plain",
                "text/plain; charset=utf-8",
                "text/plain; charset=us-ascii",
            ],
        )

        if not book_ids:
            print(f"  -> No suitable books found on shelf '{shelf}'. Trying another.")
            return None, None

        random.shuffle(book_ids)
        for item in book_ids:
            book_id = None
            if isinstance(item, (list, tuple)) and item:
                book_id = item[0]
            elif isinstance(item, int):
                book_id = item
            else:
                continue

            if book_id in processed_in_session:
                continue

            try:
                print(f"  -> Attempting to acquire book ID: {book_id}")
                book_text = textget.get_text_by_id(book_id)
                clean_text = book_text.decode("utf-8")

                if len(clean_text) > 5000:
                    title = f"Gutenberg_Book_{book_id}"
                    print(f"  -> SUCCESS: Acquired '{title}'")
                    processed_in_session.add(book_id)
                    return title, clean_text
            except Exception:
                print(f"  -> Failed to get plain text for book {book_id}. Trying next.")
                time.sleep(1)
                continue
    except Exception as e:
        print(f"[BALANCER ERROR]: A fatal error occurred during book acquisition: {e}")

    return None, None


def chunk_and_save_book(title, content, chunk_size):
    """Splits a large text into chunks and saves them as separate files."""
    print(f"  -> Processing and chunking '{title}' into ~{chunk_size:,}-word files...")
    cleaned_content = re.sub(
        r"\*\*\* START OF THE PROJECT GUTENBERG EBOOK .*?\*\*\*",
        "",
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned_content = re.sub(
        r"\*\*\* END OF THE PROJECT GUTENBERG EBOOK .*?\*\*\*",
        "",
        cleaned_content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    words = cleaned_content.split()
    chunk_count = 0
    for i in range(0, len(words), chunk_size):
        chunk = words[i : i + chunk_size]
        if not chunk:
            continue

        chunk_text = " ".join(chunk)
        chunk_count += 1

        filepath = os.path.join(NOT_CASE_DIR, f"{title}_chunk_{chunk_count}.txt")
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(chunk_text)
        except Exception as e:
            print(f"  -> ERROR saving chunk {filepath}: {e}")

    print(f"  -> Successfully created {chunk_count} new 'not_a_case' files.")
    return chunk_count


# --- Main Execution ---


def run_balancer():
    """The main logic for checking and restoring dataset balance."""
    print("\n[BALANCER ACTION]: Preparing to balance dataset...")

    os.makedirs(NOT_CASE_DIR, exist_ok=True)
    for directory in CASE_DIRECTORIES:
        os.makedirs(directory, exist_ok=True)

    cache = initialize_gutenberg_cache()
    if not cache:
        print("[BALANCER HALTED]: Could not access Gutenberg catalog.")
        return

    # --- NEW: More robust filtering logic ---
    print("  -> Filtering bookshelves for safe, English-language targets...")
    sql = "SELECT DISTINCT name FROM bookshelves;"
    all_shelves_cursor = cache.native_query(sql)
    all_shelves = [row[0] for row in all_shelves_cursor.fetchall()]

    # This regex now looks for language codes as whole words at the start
    # of a string, which is much more reliable.
    language_pattern = r"^(IT|FR|DE|PT)\b"
    contamination_pattern = r"fiction|poetry|drama|religion|mythology|juvenile|children"

    boring_shelves = [
        s
        for s in all_shelves
        if s
        and not re.search(contamination_pattern, s, re.IGNORECASE)
        and not re.search(language_pattern, s, re.IGNORECASE)
    ]
    print(f"  -> Found {len(boring_shelves)} suitable shelves for hunting.")
    # --- END NEW ---

    processed_books_this_session = set()
    case_words, _ = count_words_and_files(CASE_DIRECTORIES)
    not_case_words, _ = count_words_and_files([NOT_CASE_DIR])

    print(
        f"[BALANCER REPORT]: 'Case' Words: {case_words:,} | 'Not a Case' Words: {not_case_words:,}"
    )

    if case_words == 0:
        print(
            "[BALANCER STATUS]: No 'case' files found to balance against. Standing by."
        )
        return

    current_balance = not_case_words / case_words if case_words > 0 else 1.0
    if current_balance >= BALANCE_THRESHOLD:
        print(
            f"[BALANCER STATUS]: Dataset is already balanced ({current_balance:.2%}). Mission complete."
        )
        return

    print(
        f"[BALANCER ACTION]: Balance is off ({current_balance:.2%}). Hunting for boring books..."
    )

    avg_chunk_size = get_average_case_size()
    print(f"[BALANCER INFO]: Target chunk size will be ~{avg_chunk_size:,} words.")

    failed_attempts = 0
    max_attempts = 10  # Limit the number of attempts to avoid infinite loops
    while current_balance < BALANCE_THRESHOLD:
        # Pass the pre-filtered list to the function
        book_title, book_content = get_boring_book(
            cache, processed_books_this_session, boring_shelves
        )

        if book_title and book_content:
            chunk_and_save_book(book_title, book_content, avg_chunk_size)

            not_case_words, _ = count_words_and_files([NOT_CASE_DIR])
            current_balance = not_case_words / case_words if case_words > 0 else 1.0
            print(f"  -> New Balance: {current_balance:.2%}")
            failed_attempts
        else:
            print(
                "[BALANCER WARNING]: Failed to acquire a suitable book. Aborting for now."
            )
            failed_attempts += 1
            if failed_attempts >= max_attempts:
                print(
                    "[BALANCER ERROR]: Too many failed attempts to acquire books. Aborting."
                )
                break

    print("\n[BALANCER ACTION]: Balancing mission complete.")


if __name__ == "__main__":
    run_balancer()
