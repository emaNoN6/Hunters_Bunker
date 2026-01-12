# ==========================================================
# Hunter's Command Console - Reddit Agent (v2.4 - Fullname Fix)
# ==========================================================
import praw
import logging
from hunter.models import SourceConfig

logger = logging.getLogger("Reddit Agent")


def hunt(source: SourceConfig, credentials: dict):
	subreddit_name = source.target
	last_checked_id = source.last_known_item_id

	try:
		reddit = praw.Reddit(
				client_id=credentials['client_id'],
				client_secret=credentials['client_secret'],
				user_agent=credentials['user_agent']
		)
		subreddit = reddit.subreddit(subreddit_name)
		params = {'before': last_checked_id} if last_checked_id else {}
		new_posts = list(subreddit.new(limit=50, params=params))

		if not new_posts:
			return [], last_checked_id

		raw_leads = [_extract_post_data(post) for post in new_posts]

		# --- THE FIX: Return 'name' (t3_xyz) not 'id' (xyz) ---
		# This ensures PRAW's 'before' parameter works correctly next time.
		newest_fullname = new_posts[0].name

		return raw_leads, newest_fullname

	except Exception as e:
		logger.error(f"Reddit Hunt failed: {e}")
		return [], last_checked_id


def _extract_post_data(post) -> dict:
	"""Extracts raw post data, ensuring Permalink is the primary key."""
	lead = {
		"title":         post.title,
		"url":           f"https://www.reddit.com{post.permalink}",
		"id":            post.id,
		"subreddit":     post.subreddit.display_name,
		"author":        post.author.name if post.author else "[deleted]",
		"created_utc":   post.created_utc,
		"score":         post.score,
		"num_comments":  post.num_comments,
		"is_self":       post.is_self,
		"selftext":      post.selftext,
		"selftext_html": post.selftext_html,
		"flair":         post.link_flair_text,
		"media_type":    None,
		"original_url":  post.url
	}

	_enrich_with_media(post, lead)
	return lead


def _enrich_with_media(post, lead: dict):
	"""Analyzes the post for media content and updates the lead dictionary."""
	# Check for Reddit Video
	if getattr(post, 'is_video', False) or (post.media and "reddit_video" in post.media):
		rv = post.media.get("reddit_video", {}) if post.media else {}
		lead["media_type"] = "gif" if rv.get("is_gif") else "video"
		lead["media_url"] = rv.get("hls_url")
		lead["media_fallback_url"] = rv.get("fallback_url")
		lead["media_duration"] = rv.get("duration")
		lead["media_is_video"] = lead["media_type"] == "video"

		if not lead.get("selftext"):
			lead["selftext"] = "[Video Only]"

	# Check for Gallery
	elif getattr(post, 'is_gallery', False):
		lead["media_type"] = "gallery"
		if not lead.get("selftext"):
			lead["selftext"] = "[Gallery]"

		if getattr(post, 'media_metadata', None):
			urls = []
			for item in post.media_metadata.values():
				if 's' in item and 'u' in item['s']:
					urls.append(item['s']['u'].replace('&amp;', '&'))
			lead["media_url"] = urls

	# Check for Image (Reddit Domain)
	elif getattr(post, 'is_reddit_media_domain', False):
		if post.url.endswith(('jpg', 'jpeg', 'png', 'webp')):
			lead["media_type"] = "image"
			lead["media_url"] = post.url
			if not lead.get("selftext"):
				lead["selftext"] = "[Image Only]"

	# Check for External Video (OEmbed)
	elif post.media and 'oembed' in post.media:
		oembed = post.media['oembed']
		if oembed.get('type') == 'video':
			lead["media_type"] = "video"
			lead["media_url"] = post.url
			lead["media_provider"] = oembed.get('provider_name')
			if not lead.get("selftext"):
				lead["selftext"] = f"[{oembed.get('provider_name', 'External')} Video]"
