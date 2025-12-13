# ==========================================================
# Hunter's Command Console - Filing Clerk (v2 - Dataclass Compliant)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import logging
from hunter.models import LeadData
from hunter import db_manager

logger = logging.getLogger("Filing Clerk")


class FilingClerk:
	"""
	The master librarian for the evidence locker.
	Its sole responsibility is to take standardized LeadData objects from
	the dispatcher and correctly file them in the database using the db_manager.
	It is the final checkpoint in the data acquisition pipeline.
	"""

	def __init__(self, db_conn):
		self.db_conn = db_conn
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

				source_id = db_manager.get_source_id(lead.source_name)
				lead_uuid = db_manager.file_new_lead(self.db_conn, lead, source_id)
				# The Filing Clerk unpacks the pristine LeadData object and
				# passes its contents to the db_manager for storage.
				# This now includes the 'metadata' field.

				if lead_uuid:
					# A good practice is to update the object with its new ID
					# in case it's necessary immediately for another process.
					lead.lead_uuid = str(lead_uuid)
					logger.info(f"Filed new lead {lead.lead_uuid}: {lead.title}")
					filed_count += 1
				else:
					logger.warning(f"Failed to file lead (db_manager returned None): {lead.title}")

			except Exception as e:
				# This could be a database error or another unexpected issue.
				logger.error(f"An unexpected error occurred while filing lead '{lead.title}': {e}", exc_info=True)

		logger.info(f"Filing run complete. Successfully filed {filed_count}/{len(leads)} leads.")
