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

		# Extract URLs for duplicate checking
		lead_urls = [lead.url for lead in leads]
		existing_urls = db_manager.check_for_existing_leads_by_url(self.db_conn, lead_urls)

		new_leads_to_file = []
		for lead in leads:
			if lead.url not in existing_urls:
				new_leads_to_file.append(lead)
		#			else:
		#				logger.info(f"Skipping duplicate lead: {lead.url}")

		if not new_leads_to_file:
			logger.info("All leads were duplicates or no new leads to file.")
			return

		leads_to_process = new_leads_to_file

		filed_count = 0
		for lead in leads_to_process:
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
		logger.info(f"Filing run complete. Successfully filed {filed_count}/{len(leads_to_process)} leads.")
