#  ==========================================================
#  Hunter's Command Console
#  #
#  File: dataset_balancer.py
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

# ==========================================================
# Hunter's Command Console - Dataset Balancer v5.0
# This definitive version uses an upgraded Wikipedia agent
# to hunt for long-form articles and chunk them.
# ==========================================================

import os
import re
import random
import time
import wikipedia  # The tool we know works.

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# A list of directories where our high-quality 'case' files are stored.
CASE_DIRECTORIES = [
    os.path.join(BASE_DIR, "lore_transcripts"),
    os.path.join(BASE_DIR, "Unexplained_Transcripts"),
    os.path.join(BASE_DIR, "training_data", "forteana"),
    os.path.join(BASE_DIR, "training_data", "demonic"),
    os.path.join(BASE_DIR, "training_data", "cryptids"),
]
NOT_CASE_DIR = os.path.join(BASE_DIR, "training_data", "not_a_case")
BALANCE_THRESHOLD = 0.95

# A list of boring, high-quality Wikipedia categories known for long articles.
BORING_CATEGORIES = [
    "History of economic thought",
    "International trade law",
    "Civil engineering",
    "Tax policy",
    "Agricultural science",
    "History of accounting",
    "Industrial engineering",
]

# The minimum word count for an article to be considered "long-form".
MINIMUM_ARTICLE_WORDS = 2000

# Regex patterns for contamination check.
CONTAMINATION_PATTERNS = [
    r"ghost(s)?",
    r"haunt(ing|ed|s)?",
    r"spirit(s)?",
    r"demon(s|ic)?",
    r"supernatural",
    r"paranormal",
    r"miracle(s)?",
    r"angel(s|ic)?",
    r"ufo(s)?",
    r"alien(s)?",
    r"cryptid(s)?",
    r"monster(s)?",
    r"poltergeist",
]

# --- Helper Functions ---


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


def is_contaminated(text):
    """Checks if a text sample contains any of our forbidden keywords using regex."""
    for pattern in CONTAMINATION_PATTERNS:
        if re.search(r"\b" + pattern + r"\b", text, re.IGNORECASE):
            return True
    return False


def acquire_boring_article():
    """
    Finds a random, long, clean Wikipedia article from a specific category.
    """
    for _ in range(10):  # Try up to 10 times to find a suitable article
        try:
            category = random.choice(BORING_CATEGORIES)
            print(f"  -> Hunting for a long-form article in category: '{category}'")

            # Get a list of pages in that category
            pages = wikipedia.categorymembers(category, results=50)
#            pages = wikipedia.category(category, results=50)  # Get up to 50 pages
            if not pages:
                print(f"  -> No pages found for '{category}'. Trying another.")
                continue

            # Pick a random page and try to fetch it
            page_title = random.choice(pages)
            print(f"  -> Attempting to acquire article: '{page_title}'")
            page = wikipedia.page(page_title, auto_suggest=False, redirect=True)
            content = page.content

            # Check for contamination and length
            if not is_contaminated(content) and not is_contaminated(page_title):
                if len(content.split()) >= MINIMUM_ARTICLE_WORDS:
                    print(
                        f"    -> SUCCESS: Acquired clean, long-form article ({len(content.split()):,} words)."
                    )
                    return page_title, content
                else:
                    print(f"    -> Article is too short. Discarding and retrying...")
            else:
                print(f"    -> CONTAMINATED. Discarding and retrying...")

        except wikipedia.exceptions.PageError:
            print(f"    -> Page '{page_title}' not found or has issues. Retrying...")
        except wikipedia.exceptions.DisambiguationError:
            print(f"    -> Hit a disambiguation page. Retrying...")
        except Exception as e:
            print(f"  -> An error occurred fetching from Wikipedia: {e}. Retrying...")
        time.sleep(1)
    return None, None


def chunk_and_save_article(title, content, chunk_size):
    """Splits a large text into chunks and saves them as separate files."""
    print(f"  -> Processing and chunking '{title}' into ~{chunk_size:,}-word files...")
    words = content.split()
    chunk_count = 0
    for i in range(0, len(words), chunk_size):
        chunk = words[i : i + chunk_size]
        if not chunk:
            continue

        chunk_text = " ".join(chunk)
        chunk_count += 1

        safe_title = re.sub(r"[^\w\s-]", "", title).replace(" ", "_").lower()[:50]
        filepath = os.path.join(
            NOT_CASE_DIR, f"wiki_{safe_title}_chunk_{chunk_count}.txt"
        )
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
        f"[BALANCER ACTION]: Balance is off ({current_balance:.2%}). Hunting for boring articles..."
    )

    avg_chunk_size = get_average_case_size()
    print(f"[BALANCER INFO]: Target chunk size will be ~{avg_chunk_size:,} words.")

    while current_balance < BALANCE_THRESHOLD:
        article_title, article_content = acquire_boring_article()

        if article_title and article_content:
            chunk_and_save_article(article_title, article_content, avg_chunk_size)

            not_case_words, _ = count_words_and_files([NOT_CASE_DIR])
            current_balance = not_case_words / case_words if case_words > 0 else 1.0
            print(f"  -> New Balance: {current_balance:.2%}")
        else:
            print(
                "[BALANCER WARNING]: Failed to acquire a suitable article. Aborting for now."
            )
            break

    print("\n[BALANCER ACTION]: Balancing mission complete.")


if __name__ == "__main__":
    # You will need to install this library: pip install wikipedia
    run_balancer()
