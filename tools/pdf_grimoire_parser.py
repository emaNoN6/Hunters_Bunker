#  ==========================================================
#  Hunter's Command Console
#  #
#  File: pdf_grimoire_parser.py
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

# --- Configuration ---
# The name of your PDF file. Place it in the same folder as this script.
PDF_FILENAME = "testament of Solomon.pdf"

# The name of the output text file
OUTPUT_FILENAME = "grimoire_the_testament_of_solomon.txt"


def extract_text_from_pdf(pdf_path):
    """
    Extracts all searchable text from a PDF file.
    """
    if not os.path.exists(pdf_path):
        print(f"ERROR: Grimoire not found! Place '{pdf_path}' in the project folder.")
        return None

    print(f"Opening PDF grimoire: {pdf_path}")

    full_text = []

    try:
        # Open the PDF file in binary read mode
        with open(pdf_path, "rb") as pdf_file:
            # Create a PDF reader object
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            num_pages = len(pdf_reader.pages)
            print(f"Grimoire contains {num_pages} pages. Extracting text...")

            # Loop through every page in the PDF
            for page_num in range(num_pages):
                # Get a specific page object
                page = pdf_reader.pages[page_num]

                # Extract the text from that page
                text = page.extract_text()
                if text:
                    full_text.append(text)

        print("Successfully extracted text from all pages.")
        return "\n".join(full_text)

    except Exception as e:
        print(f"An error occurred while reading the PDF: {e}")
        return None


if __name__ == "__main__":
    # --- Installation Check ---
    try:
        import PyPDF2
    except ImportError:
        print("ERROR: Missing required library.")
        print("Please run: pip install PyPDF2")
        exit()

    extracted_content = extract_text_from_pdf(PDF_FILENAME)

    if extracted_content:
        with open(OUTPUT_FILENAME, "w", encoding="utf-8") as f:
            f.write(extracted_content)
        print(
            f"Grimoire content has been successfully transcribed to '{OUTPUT_FILENAME}'"
        )
