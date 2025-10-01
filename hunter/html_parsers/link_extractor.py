# ==========================================================
# Hunter's Command Console - Definitive Link Extractor
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import os
import logging
logger = logging.getLogger("Link Extractor")

JUNK_FILENAMES = {
	'privacy', 'terms', 'contact', 'about', 'support',
	'login', 'register', 'sitemap', 'policy'
}


def find_links(html_content):
    """
    Parses HTML content, finds all hyperlinks, and uses intelligent
    filtering to discard junk links.
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, "html.parser")
    links = []

    for a_tag in soup.find_all("a", href=True):
        url = a_tag["href"]
        text = a_tag.get_text(strip=True)

        if url.startswith("#") or url.lower().startswith('javascript:'):
            continue

        try:
            parsed_url = urlparse(url)
            path = parsed_url.path

            # --- THIS IS THE FIX ---
            # We only want to skip links that are explicitly the root path.
            # An empty path for a full domain is a valid link.
            if path == '/':
                continue
            # --- END FIX ---

            # If a path exists, check if it's a junk link
            if path:
                basename = os.path.basename(path)
                filename_without_ext, _ = os.path.splitext(basename)
                if filename_without_ext.lower() in JUNK_FILENAMES:
                    continue

        except Exception as e:
            logger.warning(f"[LINK EXTRACTOR WARNING]: Could not parse URL '{url}': {e}")
            continue

        links.append({"url": url, "text": text or url})

    return links
