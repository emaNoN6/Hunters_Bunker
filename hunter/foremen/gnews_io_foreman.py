# ==========================================================
# Hunter's Command Console - GNews.io Foreman (v2 - Dataclass Compliant)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import logging
from datetime import datetime, timezone

# Import our new, standardized data contracts
from hunter.models import LeadData, GNewsMetadata

logger = logging.getLogger("GNewsIO Foreman")
logger.addHandler(logging.NullHandler())

# Define a constant for the "unknown" publication date for clarity and easy modification.
UNKNOWN_DATE = datetime(1900, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


class GNewsIOForeman:
	"""
	The specialist for processing raw intel from the GNews.io source.
	Its sole responsibility is to translate the raw GNews.io dictionary
	format into our standardized, validated LeadData objects.
	"""

	def __init__(self, source_config):
		self.source_name = source_config.get('name', 'GNews.io')
		logger.info(f"GNews.io Foreman initialized for source: {self.source_name}")

	def translate_leads(self, raw_articles: list[dict]) -> list[LeadData]:
		"""
		Takes a list of raw article dictionaries from the GNews.io agent
		and translates them into a list of standardized LeadData objects.

		Args:
			raw_articles: A list of dictionaries directly from the gnews_io_agent.

		Returns:
			A list of validated LeadData objects, ready for the dispatcher.
		"""
		processed_leads = []
		for article in raw_articles:
			try:
				# The translation process is now a formal object creation.
				# If any required data is missing or in the wrong format,
				# this will raise an error immediately, stopping bad data
				# at the source.
				lead = self._translate_single_article(article)
				if lead:
					processed_leads.append(lead)
			except (ValueError, TypeError, KeyError) as e:
				# Catching potential errors during translation (e.g., bad date format)
				# or validation errors from the LeadData.__post_init__
				logger.error(f"Failed to translate article '{article.get('title')}'. Reason: {e}")
				continue  # Skip this lead and move to the next

		logger.info(f"Successfully translated {len(processed_leads)} articles into LeadData objects.")
		return processed_leads

	def _translate_single_article(self, article_data: dict) -> LeadData | None:
		"""
		Forge a single raw article dictionary into a LeadData object.
		"""
		# Step 1: Forge the source-specific metadata object first.
		source_details = article_data.get('source', {})
		gnews_metadata = GNewsMetadata(
				source_name=source_details.get('name'),
				source_url=source_details.get('url')
		)

		# Step 2: Parse the publication date into a proper datetime object.
		# The GNews API provides dates in ISO 8601 format with a 'Z' (Zulu time),
		# which means UTC.
		try:
			publication_date = datetime.fromisoformat(article_data['publishedAt'].replace('Z', '+00:00'))
		except (KeyError, ValueError):
			# If the date is missing or malformed, do not discard the lead.
			# Log a warning and use a fixed, queryable sentinel value to indicate "unknown".
			logger.warning(
				f"Could not parse publication date for article '{article_data.get('title')}'. Using sentinel date {UNKNOWN_DATE}.")
			publication_date = UNKNOWN_DATE

		# Step 3: Forge the final, validated LeadData object.
		# We now use our validated dataclass as the container.
		# The .get() method is used for optional fields to avoid KeyErrors.
		lead = LeadData(
				title=article_data['title'],
				url=article_data['url'],
				source_name=self.source_name,  # Use the high-level source name
				publication_date=publication_date,
				text=article_data.get('content'),
				image_url=article_data.get('image'),
				# Pack the forged metadata object into the 'metadata' field.
				metadata=gnews_metadata.__dict__
		)

		return lead
