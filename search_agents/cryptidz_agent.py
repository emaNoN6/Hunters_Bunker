import requests
from bs4 import BeautifulSoup
import time
import os
import re

# --- Configuration ---
# The starting point for our hunt
STARTING_URL = "https://cryptidz.fandom.com/wiki/Category:Supernatural"

# Where the new intel files will be stored
OUTPUT_DIR = "training_data/cryptids"

# --- Setup ---
os.makedirs(OUTPUT_DIR, exist_ok=True)


def get_all_creature_links(start_url):
    """
    Crawls the Fandom category pages to get a master list of all creature links.
    """
    print(f"--- Starting Reconnaissance on Cryptid Wiki ---")

    current_url = start_url
    all_links = set()

    while current_url:
        print(f"- Sweeping category page: {current_url}")
        try:
            response = requests.get(current_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # --- USING YOUR INTEL ---
            # We target the exact container you identified.
            members_div = soup.select_one(
                "#mw-content-text > div.category-page__members"
            )

            if not members_div:
                print(
                    "  -> Could not find the main content container on this page. Stopping."
                )
                break

            # Find all the links within that container
            found_on_page = 0
            for link_tag in members_div.find_all(
                "a", class_="category-page__member-link"
            ):
                if "href" in link_tag.attrs:
                    full_url = f"https://cryptidz.fandom.com{link_tag['href']}"
                    all_links.add(full_url)
                    found_on_page += 1
            print(f"  -> Found {found_on_page} creature links.")

            # Find the "Next" page button to continue the crawl
            next_page_link = soup.select_one("a.category-page__pagination-next")
            if next_page_link and "href" in next_page_link.attrs:
                current_url = next_page_link["href"]
                time.sleep(1)  # Be polite
            else:
                print("- No 'Next' page found. Recon complete.")
                current_url = None  # End the loop

        except requests.exceptions.RequestException as e:
            print(f"  -> ERROR fetching page: {e}. Aborting.")
            break

    print(f"\n--- Reconnaissance Complete. Total unique targets: {len(all_links)} ---")
    return list(all_links)


def scrape_creature_page(url):
    """
    Extracts the main text content from a single creature's wiki page.
    """
    print(f"  - Extracting intel from: {url}")
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        # The main content on Fandom wikis is usually in this container
        content_div = soup.select_one("#mw-content-text")
        if not content_div:
            return None, None

        # Get the title for our records
        title_tag = soup.select_one("#firstHeading")
        title = title_tag.get_text(strip=True) if title_tag else "Unknown Creature"

        # --- Surgical Cleaning ---
        # Remove known junk like info-boxes, navigation templates, and "See Also" sections
        for junk in content_div.select(
            "aside, .navbox, #see-also, .toc, .mw-editsection"
        ):
            junk.decompose()

        # Get the remaining clean text
        clean_text = content_div.get_text(separator="\n", strip=True)
        return title, clean_text

    except requests.exceptions.RequestException as e:
        print(f"    -> FAILED to extract intel: {e}")
        return None, None


# --- The Main Operation ---
if __name__ == "__main__":
    # 1. Get the list of all targets
    creature_links = get_all_creature_links(STARTING_URL)

    if creature_links:
        print(f"\n--- Beginning full extraction of {len(creature_links)} files ---")
        # 2. Loop through and extract intel from each one
        for i, link in enumerate(creature_links):
            print(f"\nProcessing target {i+1}/{len(creature_links)}...")
            title, text = scrape_creature_page(link)

            if title and text:
                # Save the intel to a file
                safe_title = re.sub(r"[^\w\s-]", "", title).replace(" ", "_").lower()
                filepath = os.path.join(OUTPUT_DIR, f"{safe_title}.txt")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(text)
                print(f"    -> Intel secured: {filepath}")

            time.sleep(1)  # Be a good hunter, don't hammer the server

    print("\n--- Cryptid Wiki Acquisition Complete ---")
    print(f"All intel files saved to: {OUTPUT_DIR}")