# ==========================================================
# Hunter's Command Console - Definitive DB Manager
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import psycopg2
import psycopg2.extras
import os
import uuid
from datetime import datetime, timezone

from . import config_manager

psycopg2.extras.register_uuid()

# --- Helper Function for Connections ---
def get_db_connection():
	try:
		db_creds = config_manager.get_pgsql_credentials()
		if not db_creds:
			print("[DB_MANAGER ERROR]: PostgreSQL credentials not found.")
			return None
		db_creds['options'] = '-c search_path=almanac,public'
		conn = psycopg2.connect(**db_creds)
		return conn

	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Could not connect to PostgreSQL: {e}")
		return None


# --- Startup & Verification Functions ---
def check_database_connection():
	conn = get_db_connection()
	if conn:
		conn.close()
		return True
	return False


def get_latest_migration_version():
	migrations_path = os.path.join(os.path.dirname(config_manager.CONFIG_FILE), "migrations")
	if not os.path.isdir(migrations_path): return 0
	files = [f for f in os.listdir(migrations_path) if f.endswith('.sql') and f.split('_')[0].isdigit()]
	return max([int(f.split('_')[0]) for f in files]) if files else 0


def verify_db_version():
	latest_script_version = get_latest_migration_version()
	conn = get_db_connection()
	if not conn: return (False, "Could not connect to PostgreSQL.")
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute("SELECT to_regclass('schema_version');")
			if cursor.fetchone()[0] is None:
				return (False, "DB schema uninitialized. Run 'python tools/run_migrations.py'")
			cursor.execute("SELECT version FROM schema_version;")
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


# --- Source Management ---
def add_source_domain(domain_data):
	sql = "INSERT INTO source_domains (domain_name, agent_type, max_concurrent_requests) VALUES (%s, %s, %s) ON CONFLICT (domain_name) DO NOTHING;"
	conn = get_db_connection()
	if not conn: return
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (domain_data['domain_name'], domain_data['agent_type'],
			                     domain_data.get('max_concurrent_requests', 1)))
			conn.commit()
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to add source domain: {e}")
		conn.rollback()
	finally:
		if conn: conn.close()


def get_source_domain_by_name(domain_name):
	sql = "SELECT * FROM source_domains WHERE domain_name = %s;"
	conn = get_db_connection()
	if not conn: return None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (domain_name,))
			return cursor.fetchone()
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get domain by name: {e}")
		return None
	finally:
		if conn: conn.close()


def add_source(source_data):
	domain = get_source_domain_by_name(source_data.get('domain_name'))
	if not domain:
		print(f"[DB_MANAGER ERROR]: Domain '{source_data.get('domain_name')}' not found.")
		return
	sql = "INSERT INTO sources (source_name, target, domain_id, purpose) VALUES (%s, %s, %s, %s) ON CONFLICT (source_name) DO NOTHING;"
	conn = get_db_connection()
	if not conn: return
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (source_data['source_name'], source_data['target'], domain['id'],
			                     source_data.get('purpose', 'lead_generation')))
			conn.commit()
			print(f"[DB_MANAGER]: Added/updated source '{source_data['source_name']}'.")
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to add source: {e}")
		conn.rollback()
	finally:
		if conn: conn.close()


def get_active_lead_sources():
	sql = "SELECT s.*, sd.agent_type FROM sources s JOIN source_domains sd ON s.domain_id = sd.id WHERE s.is_active = TRUE AND s.purpose = 'lead_generation';"
	conn = get_db_connection()
	if not conn: return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql)
			return [dict(row) for row in cursor.fetchall()]
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get active sources: {e}")
		return []
	finally:
		if conn: conn.close()


# --- Acquisition & Case Management (UUID-First Workflow) ---

def log_acquisition(lead_data, source_id):
	"""Logs a new lead to the router and the partitioned log."""
	conn = get_db_connection()
	if not conn: return None

	lead_uuid = lead_data.get('lead_uuid')
	if not lead_uuid:
		lead_uuid = str(uuid.uuid4())
		lead_data['lead_uuid'] = lead_uuid

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			router_sql = """
            INSERT INTO acquisition_router (lead_uuid, source_id, item_url, last_seen_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (lead_uuid) DO UPDATE SET last_seen_at = now()
            RETURNING lead_uuid;
            """
			cursor.execute(router_sql, (lead_uuid, source_id, lead_data.get('url')))

			log_sql = "INSERT INTO acquisition_log (lead_uuid, source_id) VALUES (%s, %s);"
			cursor.execute(log_sql, (lead_uuid, source_id))

			conn.commit()
			return lead_uuid
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to log acquisition: {e}")
		conn.rollback()
		return None
	finally:
		if conn: conn.close()


def check_acquisition_router(lead_uuid):
	"""Checks if a UUID exists in the router. Returns True if found."""
	sql = "SELECT 1 FROM acquisition_router WHERE lead_uuid = %s;"
	conn = get_db_connection()
	if not conn: return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (lead_uuid,))
			return cursor.fetchone() is not None
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to check acquisition router: {e}")
		return False
	finally:
		if conn: conn.close()


def add_case(lead_data):
	"""Promotes a lead to a case, using the new partitioned structure."""
	conn = get_db_connection()
	if not conn: return None

	lead_uuid = lead_data.get('lead_uuid')
	if not lead_uuid:
		print("[DB_MANAGER ERROR]: Cannot add case without a lead_uuid.")
		return None

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			# Insert into the main cases table
			case_sql = """
            INSERT INTO cases (lead_uuid, public_uuid, title, url, publication_date, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (url, publication_date) DO NOTHING
            RETURNING id, publication_date;
            """
			cursor.execute(case_sql, (
				lead_uuid,
				uuid.uuid4(),
				lead_data.get("title"),
				lead_data.get("url"),
				lead_data.get("publication_date"),
				'TRIAGED'
			))
			case_result = cursor.fetchone()

			# If ON CONFLICT caused nothing to be inserted, case_result will be None.
			if not case_result:
				print(f"[DB_MANAGER]: Case already exists (URL & Date): {lead_data.get('title')}")
				conn.rollback()  # Rollback the transaction to be clean
				return None

			case_id = case_result['id']
			pub_date = case_result['publication_date']

			# Insert into the content table
			content_sql = """
            INSERT INTO case_content (case_id, lead_uuid, publication_date, full_text, full_html)
            VALUES (%s, %s, %s, %s, %s);
            """
			cursor.execute(content_sql,
			               (case_id, lead_uuid, pub_date, lead_data.get("text", ""), lead_data.get("html", "")))

			# --- THIS IS THE FIX ---
			# The 'processed_status' column was removed from acquisition_log.
			# This UPDATE statement is no longer needed and has been deleted.
			# --- END FIX ---

			conn.commit()
			print(f"[DB_MANAGER]: Successfully filed new case: {lead_data.get('title')}")
			return case_id
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: An error occurred adding a case: {e}")
		if conn: conn.rollback()
		return None
	finally:
		if conn:
			conn.close()

def get_random_cases_for_testing(limit=20):
	sql = "SELECT c.*, cc.full_text, cc.full_html FROM cases c JOIN case_content cc ON c.id = cc.case_id WHERE cc.full_html IS NOT NULL AND cc.full_html != '' ORDER BY RANDOM() LIMIT %s;"
	conn = get_db_connection()
	if not conn: return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (limit,))
			cases = cursor.fetchall()
			return [dict(row) for row in cases]
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get random cases: {e}")
		return []
	finally:
		if conn: conn.close()

def get_source_by_name(name):
	sql = "SELECT * FROM sources WHERE source_name = %s;"
	conn = get_db_connection()
	if not conn: return None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (name,))
			return cursor.fetchone()
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get source by name: {e}")
		return None


def update_source_state(source_id, hunt_results):
	"""
	Updates the operational state of a source after a hunt.
	This is called by the dispatcher using the standard app user connection.

	Args:
		source_id (int): The ID of the source to update.
		hunt_results (dict): A dictionary containing the outcome, with keys like:
			'success' (bool): Whether the hunt was successful.
			'new_bookmark_id' (str, optional): The new last_known_item_id.
	"""
	conn = get_db_connection()  # Uses the standard app_user connection
	if not conn:
		return

	try:
		with conn.cursor() as cursor:
			# Use the bookmark_id from the results, falling back to the existing one if not provided
			# This handles cases like GNews where no bookmark is returned
			new_bookmark = hunt_results.get('new_bookmark_id')

			if hunt_results['success']:
				# If the hunt was successful, reset failures and update success date
				sql = """
                    UPDATE sources
                    SET
                        last_checked_date = %s,
                        last_success_date = %s,
                        consecutive_failures = 0,
                        last_known_item_id = COALESCE(%s, last_known_item_id)
                    WHERE id = %s;
                """
				cursor.execute(sql, (
					datetime.now(timezone.utc),
					datetime.now(timezone.utc),
					new_bookmark,
					source_id
				))
			else:
				# If the hunt failed, increment the failure count
				sql = """
                    UPDATE sources
                    SET
                        last_checked_date = %s,
                        last_failure_date = %s,
                        consecutive_failures = consecutive_failures + 1
                    WHERE id = %s;
                """
				cursor.execute(sql, (
					datetime.now(timezone.utc),
					datetime.now(timezone.utc),
					source_id
				))

			conn.commit()
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to update source state for source_id {source_id}: {e}")
		conn.rollback()
	finally:
		if conn:
			conn.close()
