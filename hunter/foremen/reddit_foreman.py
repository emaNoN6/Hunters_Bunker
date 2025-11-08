# ==========================================================
# Hunter's Command Console - Reddit Foreman (v2 - Dataclass Compliant)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import logging
from datetime import datetime, timezone

# Import our new, standardized data contracts
from hunter.models import LeadData, RedditMetadata

logger = logging.getLogger('Reddit Foreman')

UNKNOWN_DATE = datetime(1900, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class RedditForeman:
	"""
	The specialist for processing raw intel from the Reddit source.
	Its sole responsibility is to translate the raw PRAW submission objects
	(as dictionaries) into our standardized, validated LeadData objects.
	"""

	def __init__(self, source_config):
		self.source_name = source_config.source_name
		logger.info(f"Reddit Foreman initialized for source: {self.source_name}")

	def translate_leads(self, raw_posts: list[dict]) -> list[LeadData]:
		"""
		Takes a list of raw post dictionaries from the Reddit agent
		and translates them into a list of standardized LeadData objects.
		"""
		processed_leads = []
		for post in raw_posts:
			try:
				# The translation process is now a formal object creation.
				lead = self._translate_single_post(post)
				if lead:
					processed_leads.append(lead)
			except (ValueError, TypeError, KeyError) as e:
				logger.error(f"Failed to translate Reddit post '{post.get('title')}'. Reason: {e}")
				continue  # Skip this lead and move to the next

		logger.info(f"Successfully translated {len(processed_leads)} Reddit posts into LeadData objects.")
		return processed_leads

	def _translate_single_post(self, post_data: dict) -> LeadData | None:
		"""
		Forge a single raw post dictionary into a LeadData object.
		"""
		# Step 1: Forge the source-specific RedditMetadata object first.
		reddit_metadata = RedditMetadata(
				score=post_data.get('score'),
				author=post_data.get('author'),
				subreddit=post_data.get('subreddit'),
				num_comments=post_data.get('num_comments'),
				post_id=post_data.get('id'),
				is_self=post_data.get('is_self')
		)
		media_url = None
		media_type = None
		media_duration = None

		if post_data.get('media'):
			media = post_data.get('media')
			media_url = media.get('fallback_url')
			media_duration = media.get('duration')

			if media.get('is_gif'):
				media_type = 'gif'
			elif media_url:
				media_type = 'video'

			reddit_metadata.media_url = media_url
			reddit_metadata.media_type = media_type
			reddit_metadata.media_duration = media_duration

		# Step 2: Parse the publication date. Reddit provides a UTC timestamp.
		try:
			# PRAW provides created_utc as a float timestamp
			created_timestamp = post_data['created_utc']
			publication_date = datetime.fromtimestamp(created_timestamp, tz=timezone.utc)
		except (KeyError, ValueError):
			logger.warning(f"Could not parse created_utc for post '{post_data.get('title')}'. Using sentinel date.")
			publication_date = UNKNOWN_DATE

		# Step 3: Forge the final, validated LeadData object.
		lead = LeadData(
				title=post_data['title'],
				url=post_data['url'],
				source_name=self.source_name,
				publication_date=publication_date,
				text=post_data.get('selftext'),
				html=post_data.get('selftext_html'),
				# Use the 'thumbnail' for a consistent image, but check for 'url' if it's an image post
				image_url=post_data.get('thumbnail') if post_data.get('thumbnail') not in ['self', 'default',
				                                                                           ''] else post_data.get(
					'url'),
				metadata=reddit_metadata.__dict__
		)

		return lead
