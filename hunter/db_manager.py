# ==========================================================
# Hunter's Command Console - DB Manager (v3 - Partition & Dataclass Compliant)
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import psycopg2
import psycopg2.extras
import os
import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional

# --- Our Tools ---
from . import config_manager
from hunter.models import LeadData, METADATA_CLASS_MAP, METADATA_EXTRA_FIELDS, Asset

logger = logging.getLogger("DB Manager")

# --- Helper Function for Connections ---
def get_db_connection():
	"""Establishes a new connection to the PostgreSQL database."""
	try:
		db_creds = config_manager.get_pgsql_credentials()
		if not db_creds:
			logger.error("[DB_MANAGER ERROR]: PostgreSQL credentials not found.")
			return None
		# Ensures all operations target our primary schema by default
		db_creds['options'] = '-c search_path=almanac,public'
		conn = psycopg2.connect(**db_creds)
		return conn
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Could not connect to PostgreSQL: {e}")
		return None


def get_source_id(source_name):
	"""Fetches the ID of a source by its name."""
	conn = get_db_connection()
	if not conn:
		logger.error("get_source_id: Database connection not available.")
		return None
	sql = "SELECT id FROM sources WHERE source_name = %s;"
	try:
		with conn.cursor() as cur:
			cur.execute(sql, (source_name,))
			result = cur.fetchone()
			return result[0] if result else None
	except Exception as e:
		logger.error(f"Database error in get_source_id: {e}", exc_info=True)
		if conn: conn.rollback()

def file_new_lead(conn, lead: LeadData, source_id: int) -> uuid.UUID | None:
	"""
	The definitive, partition-aware function for filing a new lead.
	This orchestrates the existing router/staging workflow using a validated
	LeadData object.
	"""
	if not conn:
		logger.error("file_new_lead: Database connection not available.")
		return None

	try:
		# Step 1: Create or update the entry in the router for de-duplication.
		router_sql = """
                     INSERT INTO acquisition_router (lead_uuid, source_id, item_url, last_seen_at, publication_date,
                                                     status)
                     VALUES (%s, %s, %s, now(), %s, 'NEW')
                     ON CONFLICT (item_url) DO UPDATE SET last_seen_at = now()
                     RETURNING lead_uuid, (xmax = 0) AS inserted; \
		             """
		# GIT_NOTE: Uppercase NEW to match enum
		lead_uuid = uuid.uuid4()
		with conn.cursor() as cur:
			cur.execute(router_sql, (str(lead_uuid), source_id, lead.url, lead.publication_date))
			result = cur.fetchone()

		if not result:
			logger.warning(f"Could not create router entry for URL: {lead.url}")
			conn.rollback()
			return None

		router_uuid, was_inserted = result
		if not was_inserted:
			logger.info(f"Lead already exists in router (URL conflict): {lead.url}")
			conn.rollback()
			return None

		# Step 2: If new, insert content into the staging table.
		staging_sql = """
                      INSERT INTO case_data_staging (uuid, title, full_text, full_html, metadata)
                      VALUES (%s, %s, %s, %s, %s)
                      ON CONFLICT (uuid) DO NOTHING; \
		              """
		with conn.cursor() as cur:
			cur.execute(staging_sql, (
				router_uuid,
				lead.title,
				lead.text,
				lead.html,
				psycopg2.extras.Json(lead.metadata) if lead.metadata else None
			))

		conn.commit()
		logger.info(f"Successfully filed new lead {router_uuid} into staging.")
		return router_uuid

	except Exception as e:
		logger.error(f"Database error during file_new_lead: {e}", exc_info=True)
		conn.rollback()
		return None


def get_unprocessed_leads(conn) -> list[LeadData]:
	"""
	Fetches unprocessed leads from router/staging and reconstructs them
	into a list of validated LeadData objects for the GUI.
	"""
	if not conn:
		logger.error("get_unprocessed_leads: Database connection not available.")
		return []

	sql = """
          SELECT cds.title,
                 cds.full_text,
                 cds.full_html,
                 cds.metadata,
                 ar.lead_uuid,
                 ar.item_url,
                 ar.publication_date,
                 s.source_name
          FROM almanac.case_data_staging cds
                   JOIN almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
                   JOIN almanac.sources s ON ar.source_id = s.id
          WHERE ar.status = 'NEW'
          ORDER BY ar.publication_date DESC; \
	      """
	leads = []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute(sql)
			for row in cur.fetchall():
				try:
					metadata_obj = None
					raw_metadata = row['metadata']
					if raw_metadata:
						MetadataClass = METADATA_CLASS_MAP.get(row['source_name'])
						if MetadataClass:
							# Get a list of extra fields for this source
							extra_fields = METADATA_EXTRA_FIELDS.get(row['source_name'], [])

							# Split metadata into dataclass fields and extra fields
							metadata_for_class = {k: v for k, v in raw_metadata.items() if k not in extra_fields}
							extra_data = {k: v for k, v in raw_metadata.items() if k in extra_fields}

							# Create dataclass
							metadata_obj = MetadataClass(**metadata_for_class)

							# Merge back together
							metadata_dict = metadata_obj.__dict__
							metadata_dict.update(extra_data)
						else:
							metadata_dict = raw_metadata
					else:
						metadata_dict = {}

					lead = LeadData(
							title=row['title'],
							url=row['item_url'],
							source_name=row['source_name'],
							publication_date=row['publication_date'],
							text=row['full_text'],
							html=row['full_html'],
							metadata=metadata_dict,  # Use the dict, not metadata_obj.__dict__
							lead_uuid=str(row['lead_uuid'])
					)
					leads.append(lead)
				except Exception as e:
					logger.error(f"Failed to rehydrate lead {row['lead_uuid']} from DB. Error: {e}")
	except Exception as e:
		logger.error(f"Database error in get_unprocessed_leads: {e}", exc_info=True)
		if conn: conn.rollback()
	return leads


def update_lead_status(conn, lead_uuid, new_status):
	"""
	Updates the status of a lead in the acquisition_router table.
	Used for marking leads as 'IGNORED', 'PROCESSED', etc.
	"""
	if not conn:
		logging.error(f"update_lead_status: Database connection not available for lead {lead_uuid}.")
		return False

	# Validate the new_status against expected values if necessary
	valid_statuses = ['NEW', 'REVIEWING', 'PROCESSED', 'IGNORED', 'ERROR']
	if new_status not in valid_statuses:
		logging.error(f"update_lead_status: Invalid status '{new_status}' provided for lead {lead_uuid}.")
		return False

	sql = """
          UPDATE almanac.acquisition_router
          SET status       = %s,
              last_seen_at = now()
          WHERE lead_uuid = %s; \
	      """
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (new_status, lead_uuid))
			conn.commit()
			logging.info(f"Updated status for lead {lead_uuid} to {new_status}.")
			return True
	except psycopg2.Error as e:
		logging.error(f"Database error updating status for lead {lead_uuid}: {e}")
		conn.rollback()
		return False


def check_database_connection():
	"""Verifies that a connection to the database can be established."""
	conn = get_db_connection()
	if conn:
		conn.close()
		return True
	return False

def get_latest_migration_version():
	"""Finds the highest numbered migration script in the migrations folder."""
	migrations_path = os.path.join(os.path.dirname(config_manager.CONFIG_FILE), "migrations")
	if not os.path.isdir(migrations_path): return 0
	files = [f for f in os.listdir(migrations_path) if f.endswith('.sql') and f.split('_')[0].isdigit()]
	return max([int(f.split('_')[0]) for f in files]) if files else 0

def verify_db_version():
	"""Compares the schema version in the DB to the latest migration script."""
	latest_script_version = get_latest_migration_version()
	conn = get_db_connection()
	if not conn: return (False, "Could not connect to PostgreSQL.")
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute("SELECT to_regclass('almanac.schema_version');")
			if cursor.fetchone()[0] is None:
				return (False, "DB schema uninitialized. Run 'python tools/run_migrations.py'")
			cursor.execute("SELECT version FROM almanac.schema_version;")
			result = cursor.fetchone()
			db_version = result['version'] if result else 0
		if db_version < latest_script_version:
			msg = (f"DB schema out of date (DB: v{db_version}, Files: v{latest_script_version}).\n"
			       f"Run 'python tools/run_migrations.py' to update.")
			return (False, msg)
		else:
			return (True, f"DB schema is up to date (v{db_version}).")
	except Exception as e:
		return (False, f"Could not verify DB version: {e}")
	finally:
		if conn: conn.close()


def get_required_foremen(conn):
	"""Gets a list of foreman names required by the dispatcher, using the view."""
	if not conn:
		logging.error("Database connection not available.")
		return []
	foremen = []
	try:
		with conn.cursor() as cur:
			query = "SELECT agent_type FROM almanac.foreman_agents;"
			cur.execute(query)
			foremen = [row[0] for row in cur.fetchall()]
	except psycopg2.Error as e:
		logging.error(f"Error fetching required foremen from view: {e}")
		if conn: conn.rollback()
	return foremen


def get_active_sources_by_purpose(conn, purpose='lead_generation'):
	"""Fetches all active sources for a specific purpose."""
	sql = """
          SELECT s.*, sd.agent_type, sd.has_standard_foreman
          FROM sources s
                   JOIN source_domains sd ON s.domain_id = sd.id
          WHERE s.is_active = TRUE
            AND s.purpose = %s; \
	      """
	if not conn: return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (purpose,))
			return [dict(row) for row in cursor.fetchall()]
	except Exception as e:
		logger.error(f"Failed to get active sources for purpose '{purpose}': {e}")
		return []


def add_case(conn, lead_data):
	"""Promotes a lead from the triage desk to a permanent case."""
	if not conn: return None
	# NOTE: This function expects a dictionary-like object from the GUI for now.
	# It will need to be adapted to handle the full LeadData object if called from backend.
	lead_uuid = lead_data.get('lead_uuid')
	if not lead_uuid:
		logger.error("Cannot add case without a lead_uuid.")
		return None

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			# This should get the source_id from the router table based on the UUID
			cursor.execute("SELECT source_id FROM acquisition_router WHERE lead_uuid = %s;", (uuid.UUID(lead_uuid),))
			source_id_result = cursor.fetchone()
			source_id = source_id_result[0] if source_id_result else None

			case_sql = """
                       INSERT INTO cases (lead_uuid, public_uuid, source_id, source_name, title, url, publication_date,
                                          status)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'triaged')
                       ON CONFLICT (url, publication_date) DO NOTHING
                       RETURNING id, publication_date; \
			           """
			cursor.execute(case_sql, (
				uuid.UUID(lead_uuid), uuid.uuid4(),
				source_id, lead_data.get("source_name"),
				lead_data.get("title"), lead_data.get("url"),
				lead_data.get("publication_date")
			))
			case_result = cursor.fetchone()

			if not case_result:
				logger.warning(f"Case already exists: {lead_data.get('title')}")
				conn.rollback()
				return None

			case_id, pub_date = case_result['id'], case_result['publication_date']
			content_sql = """
                          INSERT INTO case_content (case_id, lead_uuid, publication_date, full_text, full_html)
                          VALUES (%s, %s, %s, %s, %s); \
			              """
			cursor.execute(content_sql,
			               (case_id, uuid.UUID(lead_uuid), pub_date, lead_data.get("text", ""),
			                lead_data.get("html", "")))

			update_router_sql = "UPDATE acquisition_router SET status = 'promoted' WHERE lead_uuid = %s;"
			cursor.execute(update_router_sql, (uuid.UUID(lead_uuid),))

			conn.commit()
			logger.info(f"Successfully filed new case: {lead_data.get('title')}")
			return case_id
	except Exception as e:
		logger.error(f"An error occurred adding a case: {e}", exc_info=True)
		if conn: conn.rollback()
		return None


def update_source_state(conn, source_id, success, new_bookmark=None):
	"""Updates the operational state of a source after a hunt."""
	if not conn: return
	try:
		with conn.cursor() as cursor:
			if success:
				sql = """
                      UPDATE sources
                      SET last_checked_date    = %s,
                          last_success_date    = %s,
                          consecutive_failures = 0,
                          last_known_item_id   = COALESCE(%s, last_known_item_id)
                      WHERE id = %s; \
				      """
				cursor.execute(sql, (datetime.now(timezone.utc), datetime.now(timezone.utc), new_bookmark, source_id))
			else:
				sql = """
                      UPDATE sources
                      SET last_checked_date    = %s,
                          last_failure_date    = %s,
                          consecutive_failures = consecutive_failures + 1
                      WHERE id = %s; \
				      """
				cursor.execute(sql, (datetime.now(timezone.utc), datetime.now(timezone.utc), source_id))
			conn.commit()
	except Exception as e:
		logger.error(f"Failed to update source state for source_id {source_id}: {e}")
		conn.rollback()

def get_all_tasks():
	sql = "SELECT * FROM system_tasks;"
	conn = get_db_connection()
	if not conn: return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql)
			return [dict(row) for row in cursor.fetchall()]
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to get all tasks: {e}")
		return []


def check_acquisition_log(url):
	sql = "SELECT 1 FROM acquisition_router WHERE item_url = %s;"
	conn = get_db_connection()
	if not conn: return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (url,))
			return cursor.fetchone() is not None
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to check acquisition log for URL {url}: {e}")
		return False


def add_router_entry(lead_data):
	"""
	Creates or updates a record in the acquisition_router.
	Uses the item_url for de-duplication.
	"""
	lead_uuid = uuid.uuid4()  # We still generate a UUID for new entries

	# --- THIS IS THE FIX ---
	# This new SQL uses ON CONFLICT on the 'item_url' to prevent duplicates.
	# If the URL exists, it just updates the timestamp.
	sql = """
          INSERT INTO acquisition_router (lead_uuid, source_id, item_url, last_seen_at, publication_date)
          VALUES (%s, %s, %s, now(), %s)
          ON CONFLICT (item_url) DO UPDATE SET last_seen_at = now()
          RETURNING lead_uuid; \
	      """
	# --- END FIX ---

	conn = get_db_connection()
	if not conn: return None
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (
				lead_uuid,
				lead_data.get('source_id'),
				lead_data.get('url'),
				lead_data.get('publication_date')
			))
			result = cursor.fetchone()
			conn.commit()
			return result[0] if result else None
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to add router entry for '{lead_data.get('title')}': {e}")
		conn.rollback()
		return None
	finally:
		if conn: conn.close()

def add_staging_data(lead_uuid, lead_data):
	"""
	Adds the content of a new lead to the case_data_staging table.

	Args:
		lead_uuid (UUID): The UUID of the lead from the router.
		lead_data (dict): A Standardized Lead Report.

	Returns:
		bool: True on success, False on failure.
	"""
	sql = """
		INSERT INTO case_data_staging (uuid, title, full_text, full_html)
		VALUES (%s, %s, %s, %s)
		ON CONFLICT (uuid) DO NOTHING;
	"""
	conn = get_db_connection()
	if not conn: return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (
				lead_uuid,
				lead_data.get('title'),
				lead_data.get('text_content'),
				lead_data.get('html_content')
			))
			conn.commit()
			return True
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to add staging data for lead '{lead_uuid}': {e}")
		conn.rollback()
		return False
	finally:
		if conn: conn.close()


def get_active_sources_by_purpose2(purpose='lead_generation'):
	"""
	Fetches all active sources for a specific purpose.
	This is the primary way the dispatcher gets its mission roster.
	"""
	sql = """
          SELECT s.*, sd.agent_type
          FROM sources s
                   JOIN source_domains sd ON s.domain_id = sd.id
          WHERE s.is_active = TRUE
            AND s.purpose = %s; \
	      """
	conn = get_db_connection()
	if not conn:
		return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (purpose,))
			return [dict(row) for row in cursor.fetchall()]
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to get active sources for purpose '{purpose}': {e}")
		return []
	finally:
		if conn:
			conn.close()

def get_staged_leads(limit=100):
	"""
	Fetches a list of untriaged leads from the staging table for the GUI.
	This version includes all the necessary data for promoting a lead to a case.
	"""
	# --- THIS IS THE FIX ---
	# We now select the item_url and publication_date from the router table.
	sql = """
          SELECT cds.id,
                 cds.title,
                 ar.lead_uuid,
                 s.source_name,
                 ar.last_seen_at,
                 ar.item_url AS url,
                 ar.publication_date
          FROM almanac.case_data_staging cds
                   JOIN
               almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
                   JOIN
               almanac.sources s ON ar.source_id = s.id
          WHERE ar.status = 'NEW'
             OR ar.status = 'REVIEWING'
          ORDER BY ar.last_seen_at DESC
          LIMIT %s; \
	      """
	# --- END FIX ---
	conn = get_db_connection()
	if not conn:
		return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (limit,))
			return [dict(row) for row in cursor.fetchall()]
	except Exception as e:
		logger.error("Failed to get staged leads", exc_info=True)
		return []
	finally:
		if conn:
			conn.close()

def get_staged_lead_details(lead_uuid):
	"""
	Fetches the full details for a single untriaged lead from the staging area.
	"""
	sql = """
          SELECT cds.title,
                 cds.full_text,
                 cds.full_html,
                 ar.item_url,
                 ar.publication_date,
                 s.source_name
          FROM almanac.case_data_staging cds
                   JOIN
               almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
                   JOIN
               almanac.sources s ON ar.source_id = s.id
          WHERE ar.lead_uuid = %s; \
	      """
	conn = get_db_connection()
	if not conn:
		return None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (lead_uuid,))
			details = cursor.fetchone()
			return dict(details) if details else None
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to get details for lead '{lead_uuid}': {e}")
		return None
	finally:
		if conn:
			conn.close()


# ==========================================================
# Search Term Morphology & API Caching (READ Operations)
# ==========================================================

def get_search_term(base_term):
	"""
	Retrieves a cached search term.

	Args:
		base_term (str): The base word to look up

	Returns:
		dict: The stored data (base_term, api_response, last_updated) or None if not found
	"""
	sql = "SELECT base_term, api_response, last_updated FROM search_terms WHERE base_term = %s;"
	conn = get_db_connection()
	if not conn:
		return None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (base_term,))
			result = cursor.fetchone()
			return dict(result) if result else None
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to get search term '{base_term}': {e}")
		return None
	finally:
		if conn:
			conn.close()


def get_all_search_terms():
	"""
	Retrieves all cached search terms for batch processing (e.g., conjugation pass).

	Returns:
		list[dict]: List of all search terms with their data
	"""
	sql = "SELECT base_term, api_response, last_updated FROM search_terms ORDER BY base_term;"
	conn = get_db_connection()
	if not conn:
		return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql)
			return [dict(row) for row in cursor.fetchall()]
	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to get all search terms: {e}")
		return []
	finally:
		if conn:
			conn.close()


def check_api_safety(service='wordsapi', min_remaining=50):
	"""
	Checks if it's safe to make more API calls based on recent usage.

	Args:
		service (str): API service name
		min_remaining (int): Minimum remaining calls required (default: 50)

	Returns:
		tuple: (is_safe: bool, remaining: int, message: str)
	"""
	# Get the most recent API call to check the current rate limit status
	sql = """
		SELECT rate_limit_remaining, rate_limit_limit, called_at
		FROM api_usage_log
		WHERE service = %s
		ORDER BY called_at DESC
		LIMIT 1;
	"""
	conn = get_db_connection()
	if not conn:
		return (False, 0, "Could not connect to database")

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (service,))
			result = cursor.fetchone()

			if not result:
				# No previous calls logged
				return (True, 0, "No previous API calls logged - proceeding with caution")

			remaining = result['rate_limit_remaining'] or 0
			limit = result['rate_limit_limit'] or 0

			if remaining < min_remaining:
				return (False, remaining, f"Only {remaining} API calls remaining (minimum: {min_remaining})")

			return (True, remaining, f"Safe to proceed: {remaining}/{limit} calls remaining")

	except Exception as e:
		logger.error(f"[DB_MANAGER ERROR]: Failed to check API safety: {e}")
		return (False, 0, f"Error checking API status: {e}")
	finally:
		if conn:
			conn.close()


def save_asset(self, asset: Asset) -> Optional[str]:
	"""
	Save an asset to the database.
	Returns the asset_id on success, None on failure.
	"""
	conn = self.get_connection()
	if not conn:
		logger.error("save_asset: Database connection not available.")
		return None

	try:
		with conn.cursor() as cur:
			sql = """
                  INSERT INTO almanac.assets (file_path, file_type, mime_type, file_size,
                                              source_type, source_uuid, original_url,
                                              related_cases, related_investigations,
                                              is_processed, is_enhanced, notes, metadata)
                  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                  RETURNING asset_id; \
			      """
			cur.execute(sql, (
				asset.file_path,
				asset.file_type,
				asset.mime_type,
				asset.file_size,
				asset.source_type,
				asset.source_uuid,
				asset.original_url,
				asset.related_cases,  # PostgreSQL handles list → array
				asset.related_investigations,
				asset.is_processed,
				asset.is_enhanced,
				asset.notes,
				psycopg2.extras.Json(asset.metadata) if asset.metadata else None
			))
			asset_id = cur.fetchone()[0]
			conn.commit()
			logger.info(f"Saved asset {asset_id}: {asset.file_path}")
			return str(asset_id)
	except Exception as e:
		logger.error(f"Failed to save asset: {e}", exc_info=True)
		if conn:
			conn.rollback()
		return None


def get_asset(self, asset_id: str) -> Optional[Asset]:
	"""
	Retrieve an asset by ID.
	Returns an Asset object or None if not found.
	"""
	conn = self.get_connection()
	if not conn:
		logger.error("get_asset: Database connection not available.")
		return None

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
			sql = "SELECT * FROM almanac.assets WHERE asset_id = %s;"
			cur.execute(sql, (asset_id,))
			row = cur.fetchone()

			if not row:
				logger.warning(f"Asset not found: {asset_id}")
				return None

			return _row_to_asset(row)
	except Exception as e:
		logger.error(f"Failed to get asset {asset_id}: {e}", exc_info=True)
		return None


def get_assets_for_case(self, case_uuid: str) -> List[Asset]:
	"""
	Get all assets linked to a specific case.
	Returns a list of Asset objects (empty list if none is found).
	"""
	conn = self.get_connection()
	if not conn:
		logger.error("get_assets_for_case: Database connection not available.")
		return []

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
			sql = "SELECT * FROM almanac.assets WHERE %s = ANY(related_cases) ORDER BY created_at DESC;"
			cur.execute(sql, (case_uuid,))
			rows = cur.fetchall()

			assets = [_row_to_asset(row) for row in rows]

			logger.info(f"Found {len(assets)} assets for case {case_uuid}")
			return assets
	except Exception as e:
		logger.error(f"Failed to get assets for case {case_uuid}: {e}", exc_info=True)
		return []


def get_assets_by_type(self, asset_type: str) -> List[Asset]:
	"""
	Get all assets of a specific type
	Returns a list of Asset objects (empty list if none found).
	"""
	conn = self.get_connection()
	if not conn:
		logger.error("get_assets_for_case: Database connection not available.")
		return []

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
			sql = "SELECT * FROM almanac.assets WHERE file_type = %s ORDER BY created_at DESC;"
			cur.execute(sql, (asset_type,))
			rows = cur.fetchall()

			assets = [_row_to_asset(row) for row in rows]

			logger.info(f"Found {len(assets)} assets of type {asset_type}")
			return assets
	except Exception as e:
		logger.error(f"Failed to get assets of type {asset_type}: {e}", exc_info=True)
		return []


def _row_to_asset(row) -> Asset:
	asset = Asset(
			asset_id=str(row['asset_id']),
			file_path=row['file_path'],
			file_type=row['file_type'],
			mime_type=row['mime_type'],
			file_size=row['file_size'],
			created_at=row['created_at'],
			source_type=row['source_type'],
			source_uuid=str(row['source_uuid']) if row['source_uuid'] else None,
			original_url=row['original_url'],
			related_cases=[str(uuid) for uuid in row['related_cases']] if row['related_cases'] else [],
			related_investigations=[str(uuid) for uuid in row['related_investigations']] if row[
				'related_investigations'] else [],
			is_processed=row['is_processed'],
			is_enhanced=row['is_enhanced'],
			notes=row['notes'],
			metadata=row['metadata'] if row['metadata'] else {}
	)
	return asset


def update_asset_metadata(self, asset_id: str, metadata: dict) -> bool:
	"""
	Update an asset's metadata (merges with existing).
	Returns True on success, False on failure.
	"""
	conn = self.get_connection()
	if not conn:
		logger.error("update_asset_metadata: Database connection not available.")
		return False

	try:
		with conn.cursor() as cur:
			# Use jsonb || operator to merge metadata
			sql = """
                  UPDATE almanac.assets
                  SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                  WHERE asset_id = %s; \
			      """
			cur.execute(sql, (psycopg2.extras.Json(metadata), asset_id))
			conn.commit()
			logger.info(f"Updated metadata for asset {asset_id}")
			return True
	except Exception as e:
		logger.error(f"Failed to update metadata for asset {asset_id}: {e}", exc_info=True)
		if conn:
			conn.rollback()
		return False
