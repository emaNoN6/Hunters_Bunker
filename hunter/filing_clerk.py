# ==========================================================
# Hunter's Command Console - Filing Clerk (v2 - Dataclass Compliant)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import logging
from hunter.models import LeadData

logger = logging.getLogger("Filing Clerk")


class FilingClerk:
	"""
	The master librarian for the evidence locker.
	Its sole responsibility is to take standardized LeadData objects from
	the dispatcher and correctly file them in the database using the db_manager.
	It is the final checkpoint in the data acquisition pipeline.
	"""

	def __init__(self, db_manager):
		self.db_manager = db_manager
		logger.info("Filing Clerk is on duty.")

	def file_leads(self, leads: list[LeadData]):
		"""
		Processes a list of LeadData objects and files them in the database.
		This is the primary entry point for the Filing Clerk.
		"""
		if not leads:
			return

		# TODO: Implement a pre-flight duplicate check against the database
		# by sending all lead.url values to a new db_manager function.
		# This will prevent wasting time trying to insert duplicates.

		filed_count = 0
		for lead in leads:
			try:
				# The Filing Clerk unpacks the pristine LeadData object and
				# passes its contents to the db_manager for storage.
				# This now includes the 'metadata' field.
				lead_uuid = self.db_manager.add_acquisition(
						source_name=lead.source_name,
						url=lead.url,
						title=lead.title,
						publication_date=lead.publication_date,
						text_content=lead.text,
						html_content=lead.html,
						image_url=lead.image_url,
						metadata=lead.metadata  # Pass the metadata dictionary
				)

				if lead_uuid:
					# A good practice is to update the object with its new ID
					# in case it's needed immediately by another process.
					lead.lead_uuid = lead_uuid
					logger.info(f"Filed new lead {lead.lead_uuid}: {lead.title}")
					filed_count += 1
				else:
					logger.warning(f"Failed to file lead (db_manager returned None): {lead.title}")

			except Exception as e:
				# This could be a database error or another unexpected issue.
				logger.error(f"An unexpected error occurred while filing lead '{lead.title}': {e}", exc_info=True)

		logger.info(f"Filing run complete. Successfully filed {filed_count}/{len(leads)} leads.")
