# ==========================================================
# Hunter's Command Console - HTTP Utilities
# This module is our central "disguise kit." Its only job
# is to generate realistic and randomized headers for our
# web-based agents to use.
# ==========================================================

import random
from urllib.parse import urlparse

# A list of modern, common User-Agent strings. By cycling through these,
# our requests won't all come from a single, identifiable signature.
USER_AGENTS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5.2 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
]

# A list of common, plausible referrers to make our traffic look more natural.
COMMON_REFERERS = [
	"https://www.google.com/",
	"https://www.bing.com/",
	"https://duckduckgo.com/",
	"https://www.facebook.com/",
	"https://t.co/",  # Twitter's link shortener
]


def get_stealth_headers(target_url=None):
	"""
	Generates a dictionary of realistic and randomized HTTP headers for making requests.

	Args:
		target_url (str, optional): The URL being requested. If provided, a
									plausible 'Referer' header will be generated.

	Returns:
		dict: A dictionary of HTTP headers.
	"""
	headers = {
		# Pick a random User-Agent for each request
		"User-Agent":                random.choice(USER_AGENTS),
		# Standard headers that make the request look more like a real browser
		"Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
		"Accept-Language":           "en-US,en;q=0.9",
		"Accept-Encoding":           "gzip, deflate, br",
		"DNT":                       "1",  # Do Not Track, a common header
		"Upgrade-Insecure-Requests": "1"
	}

	# If a target URL is provided, generate a plausible Referer.
	if target_url:
		# Create a list of possible referrers for this specific request
		possible_referers = COMMON_REFERERS + [f"{urlparse(target_url).scheme}://{urlparse(target_url).netloc}/"]
		headers["Referer"] = random.choice(possible_referers)
	else:
		# If no target is specified, just pick a common one.
		headers["Referer"] = random.choice(COMMON_REFERERS)

	return headers
