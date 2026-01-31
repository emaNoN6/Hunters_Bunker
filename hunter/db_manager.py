# ==========================================================
# Hunter's Command Console - Database Manager (v5.2 - Feature Complete)
# ==========================================================
# - Internal Connection Pool Management (Thread Safe)
# - Dual-Write Pipeline (Router + Log)
# - Metadata Rehydration Logic (using Models)
# - Full Asset & Case Management
# - Admin & Source Utilities
# ==========================================================

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Tuple

import psycopg2
from psycopg2.extras import register_uuid
from psycopg2 import pool

from hunter import config_manager
from hunter.models import LeadData, METADATA_CLASS_MAP, METADATA_EXTRA_FIELDS, Asset

logger = logging.getLogger("DB Manager")

# --- Thread-Safe Connection Pool ---
_pool = None


def _get_pool():
	global _pool
	if _pool is None:
		try:
			conn_str = config_manager.get_db_connection_string()
			# Min 1, Max 10 connections. Adjust as needed for your snow-day load.
			_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, conn_str, options="-c search_path=almanac,public")
			register_uuid()
			logger.info("Database Connection Pool initialized.")
		except Exception as e:
			logger.critical(f"Failed to initialize Connection Pool: {e}")
			raise
	return _pool


def get_conn():
	"""Returns a connection from the pool. Remember to release it!"""
	return _get_pool().getconn()


def release_conn(conn):
	"""Returns a connection to the pool."""
	_get_pool().putconn(conn)


# Alias for legacy compatibility in diagnostic scripts
get_db_connection = get_conn


def check_database_connection() -> bool:
	try:
		conn = get_conn()
		with conn.cursor() as cur:
			cur.execute("SELECT 1")
		release_conn(conn)
		return True
	except Exception:
		return False


# ==========================================================
# 1. Ingestion & Filing (The Clerk's Domain)
# ==========================================================

def file_new_lead(lead: LeadData, source_id: int) -> Optional[uuid.UUID]:
	"""
	The Master Ingestion Transaction.
	Explicitly passes the Lead UUID across tables to prevent 'sync cascade' failures.
	"""
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			# 1. Router Upsert
			router_sql = """
				INSERT INTO acquisition_router 
					(lead_uuid, source_id, item_url, publication_date, last_seen_at, status)
				VALUES (gen_random_uuid(), %s, %s, %s, NOW(), 'NEW')
				ON CONFLICT (item_url) DO UPDATE SET last_seen_at = NOW()
				RETURNING lead_uuid;
			"""
			cur.execute(router_sql, (source_id, lead.url, lead.publication_date))
			result = cur.fetchone()
			if not result:
				raise ValueError("Router failed to return a UUID.")
			lead_uuid = result[0]

			# 2. Log Entry (Synced UUID)
			cur.execute("INSERT INTO acquisition_log (lead_uuid, source_id, seen_at) VALUES (%s, %s, NOW())",
			            (lead_uuid, source_id))

			# 3. Staging Data (Synced UUID)
			staging_sql = """
				INSERT INTO case_data_staging (uuid, title, full_text, full_html, metadata)
				VALUES (%s, %s, %s, %s, %s)
				ON CONFLICT (uuid) DO UPDATE SET 
					title = EXCLUDED.title,
					full_text = EXCLUDED.full_text,
					full_html = EXCLUDED.full_html,
					metadata = EXCLUDED.metadata;
			"""
			meta_json = psycopg2.extras.Json(lead.metadata) if lead.metadata else None
			cur.execute(staging_sql, (lead_uuid, lead.title, lead.text, lead.html, meta_json))

		conn.commit()
		return lead_uuid
	except Exception as e:
		conn.rollback()
		logger.error(f"Filing failed for {lead.title}: {e}")
		return None
	finally:
		release_conn(conn)


def process_triage(results: dict):
	conn = get_conn()
	try:
		if results['CASE']:
			_promote_cases(results['CASE'])
		if results['NOT_CASE']:
			_export_for_training(conn, results['NOT_CASE'])  # Write to file first
			_mark_ignored(conn, results['NOT_CASE'])
			_delete_from_staging(conn, results['NOT_CASE'])
		if results['SKIP']:
			_mark_ignored(conn, results['SKIP'])
			_delete_from_staging(conn, results['SKIP'])
		conn.commit()
	except:
		conn.rollback()
		raise
	finally:
		release_conn(conn)


def _delete_from_staging(conn, leads):
	SQL_SKIP_CASES = """
	WITH ids AS (
		SELECT unnest(%s::uuid[]) AS uuid
	)
	DELETE FROM case_data_staging AS cds
	USING ids
	WHERE cds.uuid = ids.uuid;
	"""
	with conn.cursor() as cur:
		cur.execute(SQL_SKIP_CASES, (leads,))


def _mark_ignored(conn, leads):
	SQL_UPDATE_ROUTER = """
	WITH ids AS (
		SELECT unnest(%s::uuid[]) AS uuid
	)
	UPDATE acquisition_router ar
	SET status = 'IGNORED'
	FROM ids
	WHERE ar.lead_uuid = ids.uuid;
	"""
	with conn.cursor() as cur:
		cur.execute(SQL_UPDATE_ROUTER, (leads,))


def _mark_promoted(conn, leads):
	SQL_UPDATE_ROUTER = """
	WITH ids AS (
		SELECT unnest(%s::uuid[]) AS uuid
	)
	UPDATE acquisition_router ar
	SET status = 'PROMOTED'
	FROM ids
	WHERE ar.lead_uuid = ids.uuid;
	"""
	with conn.cursor() as cur:
		cur.execute(SQL_UPDATE_ROUTER, (leads,))


def _export_for_training(conn, uuids):
	"""Dump not-a-case leads to JSON/CSV for ML training"""
	import json
	sql = """
        SELECT cds.uuid, cds.title, cds.full_text, cds.metadata
        FROM case_data_staging cds
        WHERE cds.uuid = ANY(%s::uuid[])
    """
	with conn.cursor() as cur:
		cur.execute(sql, (uuids,))
		rows = cur.fetchall()

	# Append to training file
	with open('data/training_data/not_a_case.jsonl', 'a') as f:
		for row in rows:
			f.write(json.dumps({
				'uuid':     str(row[0]),
				'title':    row[1],
				'text':     row[2],
				'metadata': row[3],
				'label':    'not_a_case'
			}) + '\n')


def _promote_cases(uuids: List[str]):
	SQL_PROMOTE_CASES = """
	WITH ids AS (
		SELECT unnest(%s::uuid[]) AS uuid
	),
	inserted AS (
		INSERT INTO almanac.cases (
			lead_uuid,
			public_uuid,
			title,
			url,
			publication_date,
			status,
			source_id,
			source_name
		)
		SELECT
			cds.uuid,
			gen_random_uuid(),
			cds.title,
			ar.item_url,
			ar.publication_date,
			'TRIAGED',
			ar.source_id,
			s.source_name
		FROM almanac.case_data_staging AS cds
		JOIN ids ON cds.uuid = ids.uuid
		JOIN almanac.acquisition_router ar ON ar.lead_uuid = cds.uuid
		JOIN almanac.sources s ON s.id = ar.source_id
		ON CONFLICT (url, publication_date) DO NOTHING
		RETURNING id AS case_id, lead_uuid, publication_date
	)
	INSERT INTO almanac.case_content (
		case_id,
		lead_uuid,
		publication_date,
		full_text,
		full_html
	)
	SELECT
		i.case_id,
		i.lead_uuid,
		i.publication_date,
		cds.full_text,
		cds.full_html
	FROM inserted i
	JOIN almanac.case_data_staging cds ON cds.uuid = i.lead_uuid
	RETURNING case_id, lead_uuid, publication_date;
	"""

	conn = get_conn()
	try:
		with conn.cursor() as cur:

			# 1. Insert into cases + case_content (atomic pair)
			cur.execute(SQL_PROMOTE_CASES, (uuids,))
			inserted_rows = cur.fetchall()  # [(case_id, lead_uuid, publication_date), ...]

			# 2. Delete from staging (cds)
			_delete_from_staging(conn, uuids)

			# 3. Update acquisition_router
			_mark_promoted(conn, uuids)

		conn.commit()
		return inserted_rows

	except Exception as e:
		conn.rollback()
		logger.error(f"Error promoting cases: {e}")
		raise

	finally:
		release_conn(conn)

def check_for_existing_leads_by_url(urls: List[str]) -> List[str]:
	"""Checks the router for existing URLs to prevent duplicate processing."""
	if not urls:
		return []
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			cur.execute("SELECT item_url FROM acquisition_router WHERE item_url = ANY(%s)", (urls,))
			return [row[0] for row in cur.fetchall()]
	except Exception as e:
		logger.error(f"Error checking existing leads: {e}")
		return []
	finally:
		release_conn(conn)


# ==========================================================
# 2. Retrieval & Rehydration (The Foreman's Domain)
# ==========================================================

def get_unprocessed_leads() -> List[LeadData]:
	"""
	Fetches unprocessed leads and rehydrates them into validated LeadData objects.
	"""
	conn = get_conn()
	sql = """
		  SELECT cds.title, cds.full_text, cds.full_html, cds.metadata,
				 ar.lead_uuid, ar.item_url, ar.publication_date, s.source_name
		  FROM almanac.case_data_staging cds
				   JOIN almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
				   JOIN almanac.sources s ON ar.source_id = s.id
		  WHERE ar.status = 'NEW'
		  ORDER BY ar.publication_date DESC;
	"""
	leads = []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute(sql)
			for row in cur.fetchall():
				try:
					# Rehydrate metadata into standardized dict/objects
					metadata_dict = _rehydrate_metadata(row['source_name'], row['metadata'])

					lead = LeadData(
							title=row['title'],
							url=row['item_url'],
							source_name=row['source_name'],
							publication_date=row['publication_date'],
							text=row['full_text'],
							html=row['full_html'],
							metadata=metadata_dict,
							lead_uuid=row['lead_uuid']
					)
					leads.append(lead)
				except Exception as e:
					logger.error(f"Failed to rehydrate lead {row['lead_uuid']}: {e}")
	except Exception as e:
		logger.error(f"Database error in get_unprocessed_leads: {e}")
	finally:
		release_conn(conn)
	return leads


def get_lead_by_uuid(lead_uuid: str) -> Optional[LeadData]:
	"""Rehydrates a single lead by UUID."""
	conn = get_conn()
	sql = """
		  SELECT cds.title, cds.full_text, cds.full_html, cds.metadata,
				 ar.lead_uuid, ar.item_url, ar.publication_date, s.source_name
		  FROM almanac.case_data_staging cds
				   JOIN almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
				   JOIN almanac.sources s ON ar.source_id = s.id
		  WHERE ar.lead_uuid = %s;
	"""
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute(sql, (lead_uuid,))
			row = cur.fetchone()
			if not row:
				return None

			return LeadData(
					title=row['title'], url=row['item_url'], source_name=row['source_name'],
					publication_date=row['publication_date'], text=row['full_text'], html=row['full_html'],
					metadata=_rehydrate_metadata(row['source_name'], row['metadata']),
					lead_uuid=row['lead_uuid']
			)
	except Exception as e:
		logger.error(f"Failed to get lead {lead_uuid}: {e}")
		return None
	finally:
		release_conn(conn)


def get_staged_lead_details(lead_uuid: uuid.UUID) -> Optional[Dict]:
	"""Fetches full details for a single staged lead."""
	conn = get_conn()
	sql = """
		  SELECT cds.title, cds.full_text, cds.full_html, cds.metadata,
				 ar.item_url, ar.publication_date, s.source_name
		  FROM almanac.case_data_staging cds
		  JOIN almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
		  JOIN almanac.sources s ON ar.source_id = s.id
		  WHERE ar.lead_uuid = %s;
	"""
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute(sql, (lead_uuid,))
			row = cur.fetchone()
			if not row:
				return None

			details = dict(row)
			details['metadata'] = _rehydrate_metadata(row['source_name'], row['metadata'])
			return details
	except Exception as e:
		logger.error(f"Failed to get details for lead {lead_uuid}: {e}")
		return None
	finally:
		release_conn(conn)


def _rehydrate_metadata(source_name: str, raw_metadata: dict) -> dict:
	"""Internal helper to map raw JSONB to source-specific dataclass structures."""
	if not raw_metadata:
		return {}

	MetadataClass = METADATA_CLASS_MAP.get(source_name)
	if not MetadataClass:
		return raw_metadata

	extra_fields = METADATA_EXTRA_FIELDS.get(source_name, [])
	class_data = {k: v for k, v in raw_metadata.items() if k not in extra_fields}
	extra_data = {k: v for k, v in raw_metadata.items() if k in extra_fields}

	try:
		# Attempt to instantiate the validated dataclass
		obj = MetadataClass(**class_data)
		merged = obj.__dict__
		merged.update(extra_data)
		return merged
	except Exception as e:
		logger.warning(f"Metadata rehydration failed for {source_name}: {e}")
		return raw_metadata


# ==========================================================
# 3. Source & Status Management
# ==========================================================

def get_source_id(source_name: str) -> Optional[int]:
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			cur.execute("SELECT id FROM sources WHERE source_name = %s", (source_name,))
			result = cur.fetchone()
			return result[0] if result else None
	finally:
		release_conn(conn)


def get_active_sources_by_purpose(purpose='lead_generation') -> List[Dict]:
	"""Fetches active sources for the dispatcher."""
	conn = get_conn()
	sql = """
		  SELECT s.*, sd.agent_type
		  FROM sources s
		  JOIN source_domains sd ON s.domain_id = sd.id
		  WHERE s.is_active = TRUE AND s.purpose = %s;
	"""
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute(sql, (purpose,))
			return [dict(row) for row in cur.fetchall()]
	except Exception as e:
		logger.error(f"Failed to get active sources: {e}")
		return []
	finally:
		release_conn(conn)


def update_source_state(source_id: int, success: bool, new_bookmark=None):
	"""Updates operational state of a source (bookmarks)."""
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			if success:
				sql = """
					UPDATE sources
					SET last_checked_date = %s, last_success_date = %s,
						consecutive_failures = 0,
						last_known_item_id = COALESCE(%s, last_known_item_id)
					WHERE id = %s;
				"""
				cur.execute(sql, (datetime.now(timezone.utc), datetime.now(timezone.utc), new_bookmark, source_id))
			else:
				cur.execute("UPDATE sources SET last_checked_date = NOW(), last_failure_date = NOW() WHERE id = %s",
				            (source_id,))
		conn.commit()
	except Exception as e:
		conn.rollback()
		logger.error(f"Failed to update source state {source_id}: {e}")
	finally:
		release_conn(conn)


def get_required_foremen() -> List[str]:
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			cur.execute("SELECT agent_type FROM almanac.source_domains WHERE agent_type IS NOT NULL")
			return list(set([f"{row[0]}_foreman" for row in cur.fetchall()]))
	finally:
		release_conn(conn)


# TODO: call this somewhere
def update_lead_status(lead_uuid: str, new_status: str) -> bool:
	"""Updates the status of a lead in the acquisition_router."""
	conn = get_conn()
	valid_statuses = ['NEW', 'TRIAGED' 'IGNORED', 'PROMOTED']
	if new_status not in valid_statuses:
		logger.error(f"Invalid status '{new_status}' for lead {lead_uuid}")
		return False
	try:
		with conn.cursor() as cur:
			cur.execute(
					"UPDATE acquisition_router SET status = %s, last_seen_at = NOW() WHERE lead_uuid = %s",
					(new_status, lead_uuid)
			)
		conn.commit()
		return True
	except Exception as e:
		conn.rollback()
		logger.error(f"Failed to update status for {lead_uuid}: {e}")
		return False
	finally:
		release_conn(conn)


# ==========================================================
# 4. Case Management (Promotions)
# ==========================================================

def add_case(lead_data: LeadData) -> Optional[int]:
	"""Promotes a lead to a permanent case."""
	conn = get_conn()
	if not lead_data.lead_uuid:
		return None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			# Get Source ID
			cur.execute("SELECT source_id FROM acquisition_router WHERE lead_uuid = %s", (lead_data.lead_uuid,))
			sid_res = cur.fetchone()
			source_id = sid_res[0] if sid_res else None

			# Insert Case
			case_sql = """
				INSERT INTO cases (lead_uuid, public_uuid, source_id, source_name, title, url, publication_date, status)
				VALUES (%s, gen_random_uuid(), %s, %s, %s, %s, %s, 'TRIAGED')
				ON CONFLICT (url, publication_date) DO NOTHING
				RETURNING id, publication_date;
			"""
			cur.execute(case_sql, (
				lead_data.lead_uuid, source_id, lead_data.source_name,
				lead_data.title, lead_data.url, lead_data.publication_date
			))
			case_res = cur.fetchone()

			if not case_res:
				conn.rollback()
				return None

			case_id, pub_date = case_res['id'], case_res['publication_date']

			# Insert Content
			content_sql = """
				INSERT INTO case_content (case_id, lead_uuid, publication_date, full_text, full_html)
				VALUES (%s, %s, %s, %s, %s);
			"""
			cur.execute(content_sql, (case_id, lead_data.lead_uuid, pub_date, lead_data.text, lead_data.html))

			# Update Router Status
			cur.execute("UPDATE acquisition_router SET status = 'PROMOTED' WHERE lead_uuid = %s",
			            (lead_data.lead_uuid,))

		conn.commit()
		return case_id
	except Exception as e:
		conn.rollback()
		logger.error(f"Error adding case: {e}")
		return None
	finally:
		release_conn(conn)


def get_all_cases() -> List[dict]:
	conn = get_conn()
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute("SELECT * FROM cases ORDER BY publication_date DESC")
			return [dict(row) for row in cur.fetchall()]
	finally:
		release_conn(conn)


# ==========================================================
# 5. Asset Management
# ==========================================================

def save_asset(asset: Asset) -> Optional[str]:
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			sql = """
				  INSERT INTO almanac.assets (file_path, file_type, mime_type, file_size,
											  source_type, source_uuid, original_url,
											  related_cases, related_investigations,
											  is_enhanced, notes, metadata)
				  VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
				  RETURNING asset_id;
			"""
			cur.execute(sql, (
				asset.file_path, asset.file_type, asset.mime_type, asset.file_size,
				asset.source_type, asset.source_uuid, asset.original_url,
				asset.related_cases, asset.related_investigations,
				asset.is_enhanced, asset.notes,
				psycopg2.extras.Json(asset.metadata) if asset.metadata else None
			))
			asset_id = cur.fetchone()[0]
		conn.commit()
		return str(asset_id)
	except Exception as e:
		conn.rollback()
		logger.error(f"Failed to save asset: {e}")
		return None
	finally:
		release_conn(conn)


def get_assets_for_case(case_uuid: str) -> List[Asset]:
	conn = get_conn()
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
			cur.execute("SELECT * FROM almanac.assets WHERE %s = ANY(related_cases) ORDER BY created_at DESC",
			            (case_uuid,))
			rows = cur.fetchall()
			return [_row_to_asset(row) for row in rows]
	finally:
		release_conn(conn)


def _row_to_asset(row) -> Asset:
	return Asset(
			asset_id=row['asset_id'],
			file_path=row['file_path'],
			file_type=row['file_type'],
			mime_type=row['mime_type'],
			file_size=row['file_size'],
			created_at=row['created_at'],
			source_type=row['source_type'],
			source_uuid=row['source_uuid'] if row['source_uuid'] else None,
			original_url=row['original_url'],
			related_cases=[u for u in (row['related_cases'] or [])],
			related_investigations=[u for u in (row['related_investigations'] or [])],
			is_enhanced=row['is_enhanced'],
			notes=row['notes'],
			metadata=row['metadata'] or {}
	)


# ==========================================================
# 6. Admin & Migration Tools
# ==========================================================

def get_latest_migration_version() -> int:
	migrations_path = os.path.join(os.path.dirname(config_manager.CONFIG_FILE), "migrations")
	if not os.path.isdir(migrations_path): return 0
	files = [f for f in os.listdir(migrations_path) if f.endswith('.sql') and f.split('_')[0].isdigit()]
	return max([int(f.split('_')[0]) for f in files]) if files else 0


def verify_db_version() -> Tuple[bool, str]:
	"""Verifies DB schema version matches expected state."""
	latest_script = get_latest_migration_version()
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			cur.execute("SELECT to_regclass('almanac.schema_version')")
			if cur.fetchone()[0] is None:
				return False, "DB schema uninitialized."
			cur.execute("SELECT version FROM schema_version")
			res = cur.fetchone()
			db_ver = res[0] if res else 0

		if db_ver < latest_script:
			return False, f"DB Outdated (DB: v{db_ver}, Scripts: v{latest_script})"
		return True, f"DB Valid (v{db_ver})"
	except Exception as e:
		return False, f"Verification failed: {e}"
	finally:
		release_conn(conn)


def get_all_tasks() -> List[Dict]:
	conn = get_conn()
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
			cur.execute("SELECT * FROM system_tasks")
			return [dict(row) for row in cur.fetchall()]
	finally:
		release_conn(conn)


def remove_from_cds(uuid):
	conn = get_conn()
	try:
		with conn.cursor() as cur:
			cur.execute("DELETE FROM case_data_staging WHERE uuid = %s", (uuid,))
		conn.commit()
	except Exception as e:
		conn.rollback()
		logger.error(f"Failed to remove from case_data_staging for {uuid}: {e}")
