#  ==========================================================
#  Hunter's Command Console
#  #
#  File: link_extractor.py
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

# hunter/html_parsers/link_extractor.py

from bs4 import BeautifulSoup
import re

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
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, "html.parser")
    links = []
    for a_tag in soup.find_all("a", href=True):
        url = a_tag["href"]
        text = a_tag.get_text(strip=True)
        if url.startswith("#"):
            continue
        if not any(re.search(p, url, re.IGNORECASE) for p in JUNK_LINK_PATTERNS):
            links.append({"url": url, "text": text or url})
    return links
