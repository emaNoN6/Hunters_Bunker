# ==========================================================
# Hunter's Command Console
#
# File:    link_extractor.py
# Version: 2.0.0
#
# Copyright (c) 2025, M. Stilson & Codex
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the MIT License. See the LICENSE file for details.
# ==========================================================

from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import os

# --- The New, Smarter Filter ---
# This is now a simple set of the core "junk" filenames. We will check
# against this list in a more intelligent way.
JUNK_FILENAMES = {
	'privacy', 'terms', 'contact', 'about', 'support',
	'login', 'register', 'sitemap', 'policy'
}


def find_links(html_content):
	"""
    Parses HTML content, finds all hyperlinks, and uses a new, more
    intelligent filtering logic to discard junk links.
    """
	if not html_content:
		return []

	soup = BeautifulSoup(html_content, "html.parser")
	links = []

	for a_tag in soup.find_all("a", href=True):
		url = a_tag["href"]
		text = a_tag.get_text(strip=True)

		# Basic filter for anchors and javascript calls
		if url.startswith("#") or url.lower().startswith('javascript:'):
			continue

		try:
			# --- THE NEW, C-PROGRAMMER'S LOGIC IS HERE ---
			# 1. Parse the URL into its constituent parts, like a struct.
			parsed_url = urlparse(url)

			# 2. Get just the path component (e.g., "/some/folder/about.html")
			path = parsed_url.path
			if not path or path == '/':
				continue  # Skip root links

			# 3. Get the final component of the path (the "filename")
			#    os.path.basename works on URL paths too.
			basename = os.path.basename(path)

			# 4. Strip the extension from the filename (e.g., "about.html" -> "about")
			filename_without_ext, _ = os.path.splitext(basename)

			# 5. Now, we do a clean, precise check.
			if filename_without_ext.lower() in JUNK_FILENAMES:
				continue  # This is a junk link, like /about.html or /contact

		except Exception as e:
			# Fallback for weird, un-parseable URLs
			print(f"[LINK EXTRACTOR WARNING]: Could not parse URL '{url}': {e}")
			continue

		links.append({"url": url, "text": text or url})

	return links
