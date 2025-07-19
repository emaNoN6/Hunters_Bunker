# html_parsers/link_extractor.py

from bs4 import BeautifulSoup
import re

# A list of keywords to identify and discard junk links.
JUNK_LINK_PATTERNS = [
    "privacy",
    "terms",
    "contact",
    "about",
    "support",
    "login",
    "register",
    "sitemap",
    "javascript:void",
]


def find_links(html_content):
    """
    Parses HTML content, finds all hyperlinks, filters out junk,
    and returns a clean list of (url, text) tuples.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    links = []

    for a_tag in soup.find_all("a", href=True):
        url = a_tag["href"]
        text = a_tag.get_text(strip=True)

        # Skip if it's just an internal page anchor
        if url.startswith("#"):
            continue

        # Junk filter
        is_junk = False
        for pattern in JUNK_LINK_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                is_junk = True
                break

        if not is_junk:
            links.append({"url": url, "text": text or url})

    return links
