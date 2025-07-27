#  ==========================================================
#  Hunter's Command Console
#  #
#  File: transcript_auditor.py
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

import os

# --- Configuration ---
# The directory you want to investigate.
TARGET_DIR = "g:\\My Drive\\lore_transcripts"

def run_audit():
    TOTAL_WORDS = 0
    """
    Audits all .txt files in a directory, reporting their size and word count,
    and sorting them to easily find outliers.
    """
    print(f"--- Running Coroner's Report on directory: '{TARGET_DIR}' ---")

    if not os.path.exists(TARGET_DIR):
        print(f"ERROR: Directory not found. Aborting.")
        return

    file_stats = []

    # First, gather the stats for every file
    for filename in os.listdir(TARGET_DIR):
        if filename.endswith(".txt"):
            filepath = os.path.join(TARGET_DIR, filename)
            try:
                # Get file size in kilobytes
                file_size_kb = os.path.getsize(filepath) / 1024

                # Get word count
                with open(filepath, "r", encoding="utf-8") as f:
                    word_count = len(f.read().split())
                TOTAL_WORDS += word_count

                file_stats.append(
                    {"name": filename, "size_kb": file_size_kb, "words": word_count}
                )

            except Exception as e:
                print(f"Could not process {filename}: {e}")

    if not file_stats:
        print("No .txt files found to audit.")
        return

    # --- The most important part: Sort the results ---
    # We sort by word count, from smallest to largest. The problem files
    # will be right at the top of the list.
    file_stats.sort(key=lambda x: x["words"])

    # --- Print the Report ---
    print("\n--- Audit Report (Sorted by Word Count) ---")
    print("-" * 60)
    print(f"{'Filename':<40} {'Size (KB)':>10} {'Word Count':>10}")
    print("-" * 60)

    for stat in file_stats:
        # We'll truncate the filename if it's too long, to keep the table clean
        truncated_name = (
            (stat["name"][:37] + "...") if len(stat["name"]) > 40 else stat["name"]
        )
        print(f"{truncated_name:<40} {stat['size_kb']:>10.2f} {stat['words']:>10,}")

    print("-" * 60)
    print(f"\nAudit complete. Found {len(file_stats)} files.")
    print(f"Total words across all files: {TOTAL_WORDS:,}")
    print(
        "Recommendation: Inspect the files at the top of this list for incompleteness."
    )


if __name__ == "__main__":
    run_audit()
