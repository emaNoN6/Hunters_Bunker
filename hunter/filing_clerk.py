# ==========================================================
# Hunter's Command Console - Filing Clerk (v3 - Lean)
# ==========================================================

import logging
from hunter.models import LeadData
from hunter import db_manager

logger = logging.getLogger("Filing Clerk")


class FilingClerk:
	"""
	The master librarian. No longer carries a database connection;
	it delegates all storage operations to the db_manager.
	"""

	def __init__(self):
		logger.info("Filing Clerk is on duty.")

	def file_leads(self, leads: list[LeadData]):
		if not leads:
			return

		# 1. Deduplication check
		lead_urls = [lead.url for lead in leads]
		existing_urls = db_manager.check_for_existing_leads_by_url(lead_urls)

		new_leads_to_file = [l for l in leads if l.url not in existing_urls]

		if not new_leads_to_file:
			logger.info("All leads were duplicates or no new leads to file.")
			return

		# 2. Sequential Filing
		filed_count = 0
		for lead in new_leads_to_file:
			try:
				source_id = db_manager.get_source_id(lead.source_name)

				# file_new_lead now handles Router, Log, and Staging in one transaction
				lead_uuid = db_manager.file_new_lead(lead, source_id)

				if lead_uuid:
					lead.lead_uuid = lead_uuid
					logger.info(f"Filed new lead {lead.lead_uuid}: {lead.title}")
					filed_count += 1
				else:
					logger.warning(f"Failed to file lead (Manager returned None): {lead.title}")

			except Exception as e:
				logger.error(f"Error filing lead '{lead.title}': {e}", exc_info=True)

		logger.info(f"Filing complete. {filed_count}/{len(new_leads_to_file)} new leads added.")
