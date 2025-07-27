#  ==========================================================
#  Hunter's Command Console
#  #
#  File: data_auditor.py
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
import shutil
import re  # Import the regular expressions library

# --- Configuration ---
# The folder we are going to audit
AUDIT_DIR = "g:/My Drive/training_data/not_a_case"

# Where to move suspicious files for your final judgment
REVIEW_DIR = "g:/My Drive/training_data/needs_manual_review"

# --- NEW: Regex-Powered Keyword Patterns ---
# This list now contains regex patterns.
# \b is a "word boundary" - it ensures we don't match 'angel' inside 'strangely'.
SUSPICIOUS_PATTERNS = [
    r"\bangel(s|ic)?\b",  # Matches angel, angels, angelic
    r"\b(miracle|miraculous)\b",  # Matches miracle, miraculous
    r"\bdivine\b",
    r"\bheaven(ly)?\b",  # Matches heaven, heavenly
    r"\b(seraph|cherub)\w*\b",  # Matches seraph, seraphim, cherub, etc.
    r"\bapparition(s)\b",
    r"spontaneous\s+remission",  # Matches the phrase
    r"unexplained\s+healing",  # Matches the phrase
    r"\bstigmata\b",
    r"\bprophe(cy|t|size)\w*\b",  # Matches prophecy, prophet, prophesize, etc.
    r"\bomen(s)"
]

# We pre-compile the regex patterns for efficiency. This is a good practice.
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]


def audit_not_a_case_folder():
    """
    Sweeps the 'not_a_case' folder for potentially miscategorized files
    using powerful regular expression matching.
    """
    print("--- Starting Data Audit Protocol (Regex Enabled) ---")

    os.makedirs(REVIEW_DIR, exist_ok=True)

    if not os.path.exists(AUDIT_DIR):
        print(f"Error: Audit directory '{AUDIT_DIR}' not found. Aborting.")
        return

    print(f"Auditing folder: '{AUDIT_DIR}'...")
    files_to_check = os.listdir(AUDIT_DIR)
    suspicious_count = 0

    for filename in files_to_check:
        filepath = os.path.join(AUDIT_DIR, filename)

        if not os.path.isfile(filepath):
            continue

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            # --- The Regex Search ---
            # We now loop through our compiled patterns and search the content.
            for pattern in COMPILED_PATTERNS:
                if pattern.search(content):
                    print(
                        f"  -> Suspicious pattern '{pattern.pattern}' found in: {filename}"
                    )

                    destination_path = os.path.join(REVIEW_DIR, filename)
                    shutil.move(filepath, destination_path)
                    print(f"     Moved to '{REVIEW_DIR}' for manual review.")
                    suspicious_count += 1
                    break  # Move to the next file once one match is found

        except Exception as e:
            print(f"  - Could not process file {filename}: {e}")

    print("\n--- Audit Complete ---")
    if suspicious_count > 0:
        print(f"Found and moved {suspicious_count} potentially contaminated files.")
    else:
        print("No contaminated files found based on current patterns.")


if __name__ == "__main__":
    audit_not_a_case_folder()
