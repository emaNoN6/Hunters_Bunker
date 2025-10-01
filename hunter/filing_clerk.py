# ==========================================================
# Hunter's Command Console - Definitive Filing Clerk
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

from . import db_manager
import logging
logger = logging.getLogger("Filing Clerk")

def file_new_lead(standardized_report):
    """
    Performs the full, multistep ritual for filing a new lead.
    This is the single point of entry for new data into the system.

    Args:
        standardized_report (dict): A clean, standardized report from a Foreman.

    Returns:
        bool: True if filing was successful, False otherwise.
    """
    title = standardized_report.get('title', 'Untitled Lead')
    logger.info(f"[FILING_CLERK]: Receiving new lead for filing: '{title}'")

    # --- Step 1: Create the entry in the acquisition_router ---
    # This is the "front desk" logbook. It must be created first.
    lead_uuid = db_manager.add_router_entry(standardized_report)

    if not lead_uuid:
        logger.error(f"[FILING_CLERK ERROR]: Failed to create router entry for '{title}'. Aborting file.")
        return False

    # --- Step 2: File the content in the staging area ---
    # This is the "evidence locker" for untriaged content.
    success = db_manager.add_staging_data(lead_uuid, standardized_report)

    if not success:
        logger.error(f"[FILING_CLERK ERROR]: Failed to file staging data for lead '{lead_uuid}'.")
        # In a future version, we might want to roll back the router entry here.
        return False

    logger.info(f"[FILING_CLERK]: Successfully filed new lead '{title}' with UUID: {lead_uuid}")
    return True
