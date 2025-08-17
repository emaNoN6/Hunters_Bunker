# ==========================================================
# Hunter's Command Console - Definitive DB Manager
# Copyright (c) 2025, M. Stilson & Codex
# ==========================================================

import psycopg2
import psycopg2.extras
import os
import uuid
from datetime import datetime

from . import config_manager


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
		lead_uuid = str(uuid.uuid4())  # Generate UUID if agent didn't
		lead_data['lead_uuid'] = lead_uuid

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			# 1. Upsert into the router table
			router_sql = """
            INSERT INTO acquisition_router (lead_uuid, source_id, item_url, last_seen_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (lead_uuid) DO UPDATE SET last_seen_at = now()
            RETURNING lead_uuid;
            """
			cursor.execute(router_sql, (lead_uuid, source_id, lead_data.get('url')))

			# 2. Append to the historical log
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
		return False  # Assume not found on error
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
            RETURNING id, publication_date;
            """
			cursor.execute(case_sql, (
				lead_uuid,
				uuid.uuid4(),  # Generate a new public_uuid for the case
				lead_data.get("title"),
				lead_data.get("url"),
				lead_data.get("publication_date"),
				'TRIAGED'
			))
			case_result = cursor.fetchone()
			if not case_result: raise Exception("Failed to create case.")
			case_id = case_result['id']
			pub_date = case_result['publication_date']

			# Insert into the content table
			content_sql = """
            INSERT INTO case_content (case_id, lead_uuid, publication_date, full_text, full_html)
            VALUES (%s, %s, %s, %s, %s);
            """
			cursor.execute(content_sql,
			               (case_id, lead_uuid, pub_date, lead_data.get("text", ""), lead_data.get("html", "")))

			# Update the acquisition log status
			update_sql = "UPDATE acquisition_log SET processed_status = 'PROCESSED', processed_at = now() WHERE lead_uuid = %s;"
			cursor.execute(update_sql, (lead_uuid,))

			conn.commit()
			print(f"[DB_MANAGER]: Successfully filed new case: {lead_data.get('title')}")
			return case_id
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: An error occurred adding a case: {e}")
		if conn: conn.rollback()
		return None
	finally:
		if conn: conn.close()
