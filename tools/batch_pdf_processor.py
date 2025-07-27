#  ==========================================================
#  Hunter's Command Console
#  #
#  File: batch_pdf_processor.py
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

import PyPDF2
import os
import re

# --- Configuration ---
# The folder where you will place all your Fortean Times PDF files.
SOURCE_PDF_DIR = "fortean_times_pdfs"

# The folder where the clean text files will be saved.
# We're creating a new category for our model to learn.
OUTPUT_TXT_DIR = "training_data/forteana"

# --- Setup ---
# Create the source and destination directories if they don't exist,
# so you have a place to put your PDFs.
os.makedirs(SOURCE_PDF_DIR, exist_ok=True)
os.makedirs(OUTPUT_TXT_DIR, exist_ok=True)


def batch_extract_text_from_pdfs():
    """
    Finds all PDFs in the source directory, extracts their text,
    and saves them as .txt files in the output directory.
    """
    print(f"--- Starting Batch PDF Processing Protocol ---")
    print(f"Source Folder: '{SOURCE_PDF_DIR}'")
    print(f"Output Folder: '{OUTPUT_TXT_DIR}'")

    # Get a list of all files in the source directory
    try:
        pdf_files = [
            f for f in os.listdir(SOURCE_PDF_DIR) if f.lower().endswith(".pdf")
        ]
    except FileNotFoundError:
        print(f"ERROR: Source directory not found: '{SOURCE_PDF_DIR}'")
        print("Please create it and add your Fortean Times PDFs.")
        return

    if not pdf_files:
        print("\nNo PDF files found in the source directory. Aborting.")
        return

    print(f"\nFound {len(pdf_files)} PDF files to process.")
    success_count = 0
    fail_count = 0

    # Loop through every PDF file found
    for pdf_filename in pdf_files:
        pdf_path = os.path.join(SOURCE_PDF_DIR, pdf_filename)

        # Create a clean name for the output .txt file
        # e.g., "Fortean_Times_Issue_190.pdf" -> "fortean_times_issue_190.txt"
        base_name = os.path.splitext(pdf_filename)[0]
        txt_filename = f"{base_name.lower().replace(' ', '_')}.txt"
        txt_path = os.path.join(OUTPUT_TXT_DIR, txt_filename)

        # Check if we've already processed this file to save time
        if os.path.exists(txt_path):
            print(f"- Skipping '{pdf_filename}' (text file already exists).")
            continue

        print(f"\n- Processing '{pdf_filename}'...")
        full_text = []
        try:
            with open(pdf_path, "rb") as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    text = page.extract_text()
                    if text:
                        full_text.append(text)

            # Join all the page text together
            final_text = "\n".join(full_text)

            # Save the final text to the output file
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(final_text)

            print(f"  -> SUCCESS: Extracted and saved to '{txt_path}'")
            success_count += 1

        except Exception as e:
            print(f"  -> ERROR: Failed to process '{pdf_filename}': {e}")
            fail_count += 1

    print("\n--- Batch Processing Complete ---")
    print(f"Successfully processed: {success_count} files.")
    print(f"Failed to process: {fail_count} files.")


if __name__ == "__main__":
    try:
        import PyPDF2
    except ImportError:
        print("ERROR: Missing required library.")
        print("Please run: pip install PyPDF2")
        exit()

    batch_extract_text_from_pdfs()
