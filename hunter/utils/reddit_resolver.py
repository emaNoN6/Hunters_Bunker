#  ==========================================================
#   Hunter's Command Console
#
#   File: reddit_resolver.py
#   Last modified: 2026-02-01 16:23:01
#
#   Copyright (c) 2026 emaNoN & Codex
#
#  ==========================================================
import requests
import logging


def get_fresh_hls_url(permalink):
	"""
	Hits Reddit API to find the fresh HLS (.m3u8) playlist.
	Returns None if failed.
	"""
	try:
		url = permalink.rstrip("/") + ".json"
		headers = {'User-Agent': 'HuntersConsole/1.0'}

		r = requests.get(url, headers=headers, timeout=5)
		if r.status_code != 200: return None

		data = r.json()
		post_data = data[0]['data']['children'][0]['data']

		def get_hls(media):
			if media and 'reddit_video' in media:
				return media['reddit_video'].get('hls_url')
			return None

		# Try main post, then crosspost
		return get_hls(post_data.get('secure_media')) or \
			(post_data.get('crosspost_parent_list') and get_hls(
					post_data['crosspost_parent_list'][0].get('secure_media')))

	except Exception as e:
		logging.error(f"HLS Resolve Error: {e}")
		return None
