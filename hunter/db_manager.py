# ==========================================================
# Hunter's Command Console - Database Manager (Definitive)
# This version is fully synchronized with the final, squashed
# 001_initial_schema.sql and the refactored project structure.
# ==========================================================

import psycopg2
import psycopg2.extras
import os
import uuid
from datetime import datetime

# --- Our Custom Tools ---
from . import config_manager


# --- Helper Function for Connections ---

def get_db_connection():
    """Creates and returns a connection to the PostgreSQL database."""
    try:
        db_creds = config_manager.get_pgsql_credentials()
        if not db_creds:
            print("[DB_MANAGER ERROR]: PostgreSQL credentials not found in config.ini")
            return None
        conn = psycopg2.connect(**db_creds)
        return conn
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Could not connect to PostgreSQL database: {e}")
        return None

# --- Startup & Verification Functions ---

def check_database_connection():
	"""A simple function to test if we can connect to the database."""
	conn = get_db_connection()
	if conn:
		print("[DB_MANAGER]: PostgreSQL connection successful.")
		conn.close()
		return True
	else:
		print("[DB_MANAGER]: PostgreSQL connection failed.")
		return False


def get_latest_migration_version():
	"""Finds the version number of the latest migration file on disk."""
	migrations_path = os.path.join(os.path.dirname(config_manager.CONFIG_FILE), "migrations")
	if not os.path.isdir(migrations_path): return 0
	migration_files = [f for f in os.listdir(migrations_path) if f.endswith('.sql') and f.split('_')[0].isdigit()]
	if not migration_files: return 0
	return max([int(f.split('_')[0]) for f in migration_files])


def verify_db_version():
	"""Performs a pre-flight check on the database schema version."""
	latest_script_version = get_latest_migration_version()
	conn = get_db_connection()
	if not conn: return (False, "Could not connect to PostgreSQL database.")
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute("SELECT to_regclass('public.schema_version');")
			if cursor.fetchone()[0] is None:
				msg = "DB schema is uninitialized. Please run 'python tools/run_migrations.py'"
				return (False, msg)
			cursor.execute("SELECT version FROM schema_version;")
			result = cursor.fetchone()
			db_version = result['version'] if result else 0
		if db_version < latest_script_version:
			msg = (f"Database schema is out of date (DB: v{db_version}, Files: v{latest_script_version}).\n"
			       f"Please run 'python tools/run_migrations.py' to update.")
			return (False, msg)
		else:
			msg = f"Database schema is up to date (v{db_version})."
			return (True, msg)
	except Exception as e:
		return (False, f"Could not verify database version: {e}")
	finally:
		if conn: conn.close()


# --- Source Management Functions ---

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


def add_source(source_data):
	domain_name = source_data.get('domain_name')
	if not domain_name:
		print("[DB_MANAGER ERROR]: Cannot add source without a 'domain_name'.")
		return
	domain = get_source_domain_by_name(domain_name)
	if not domain:
		print(f"[DB_MANAGER ERROR]: Domain '{domain_name}' not found. Please seed domains first.")
		return
	domain_id = domain['id']
	sql = "INSERT INTO sources (source_name, target, strategy, keywords, purpose, domain_id) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (source_name) DO NOTHING;"
	conn = get_db_connection()
	if not conn: return
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (source_data['source_name'], source_data['target'], source_data.get('strategy'),
			                     source_data.get('keywords'), source_data.get('purpose', 'lead_generation'), domain_id))
			conn.commit()
			print(f"[DB_MANAGER]: Added/updated source '{source_data['source_name']}'.")
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to add source: {e}")
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


def get_active_lead_sources():
	"""Retrieves all sources for lead generation, joining with the domain."""
	sql = "SELECT s.*, sd.agent_type FROM sources s JOIN source_domains sd ON s.domain_id = sd.id WHERE s.is_active = TRUE AND s.purpose = 'lead_generation';"
	conn = get_db_connection()
	if not conn: return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql)
			sources = cursor.fetchall()
			return [dict(row) for row in sources]
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get active sources: {e}")
		return []
	finally:
		if conn: conn.close()


# --- Case Management Functions ---

def add_case(lead_data):
	"""Adds a confirmed lead to the new, separated cases and case_content tables."""
	conn = get_db_connection()
	if not conn: return None
	if not lead_data.get("url"):
		print("[DB_MANAGER WARNING]: Attempted to add a case with no URL. Aborting.")
		return None
	case_id = None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute("SELECT id FROM cases WHERE url = %s;", (lead_data.get("url"),))
			existing_case = cursor.fetchone()
			if existing_case:
				print(f"[DB_MANAGER]: Case already exists in archive: {lead_data.get('title')}")
				return existing_case['id']

			case_sql = "INSERT INTO cases (public_uuid, title, url, source_name, publication_date, status, category) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id;"
			new_uuid = str(uuid.uuid4())
			cursor.execute(case_sql, (new_uuid, lead_data.get("title", "No Title"), lead_data.get("url"),
			                          lead_data.get("source", "Unknown"), lead_data.get("publication_date"), 'NEW',
			                          'UNCATEGORIZED'))
			result = cursor.fetchone()
			if not result: raise Exception("Failed to retrieve new case ID after insert.")
			case_id = result['id']

			content_sql = "INSERT INTO case_content (case_id, full_text, full_html) VALUES (%s, %s, %s);"
			cursor.execute(content_sql, (case_id, lead_data.get("text", ""), lead_data.get("html", "")))

			conn.commit()
			print(f"[DB_MANAGER]: Successfully filed new case: {lead_data.get('title')}")
			return case_id
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: An error occurred adding a case: {e}")
		if conn: conn.rollback()
		return None
	finally:
		if conn: conn.close()


def get_random_cases_for_testing(limit=20):
	"""
	Fetches a random sample of cases for testing. It first tries to get
	cases with HTML content, but falls back to any cases if none are found.
	"""
	conn = get_db_connection()
	if not conn: return []

	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			# --- The New, Smarter Logic ---
			# 1. First, try the "perfect" query for cases with HTML.
			sql_html = """
                       SELECT c.id, \
                              c.public_uuid, \
                              c.title, \
                              c.url, \
                              c.source_name AS source,
                              cc.full_text, \
                              cc.full_html
                       FROM cases c
                                JOIN case_content cc ON c.id = cc.case_id
                       WHERE cc.full_html IS NOT NULL \
                         AND cc.full_html != ''
                       ORDER BY RANDOM()
                       LIMIT %s; \
			           """
			cursor.execute(sql_html, (limit,))
			cases = cursor.fetchall()

			# 2. If we came back empty-handed, run the fallback query.
			if not cases:
				print("[DB_MANAGER DEBUG]: No cases with HTML found. Falling back to any cases.")
				sql_any = """
                          SELECT c.id, \
                                 c.public_uuid, \
                                 c.title, \
                                 c.url, \
                                 c.source_name AS source,
                                 cc.full_text, \
                                 cc.full_html
                          FROM cases c
                                   JOIN case_content cc ON c.id = cc.case_id
                          ORDER BY RANDOM()
                          LIMIT %s; \
				          """
				cursor.execute(sql_any, (limit,))
				cases = cursor.fetchall()

			return [dict(row) for row in cases]

	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get random cases: {e}")
		return []
	finally:
		if conn: conn.close()


# --- System Task & Acquisition Log Functions ---

def get_all_tasks():
	"""Fetches all tasks from the system_tasks table."""
	sql = "SELECT * FROM system_tasks ORDER BY task_name;"
	conn = get_db_connection()
	if not conn: return []
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql)
			tasks = cursor.fetchall()
			return [dict(row) for row in tasks]
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to get all system tasks: {e}")
		return []
	finally:
		if conn: conn.close()


def check_acquisition_log(item_url):
	"""Checks if an item has already been processed or ignored."""
	sql = "SELECT status FROM acquisition_log WHERE item_url = %s;"
	conn = get_db_connection()
	if not conn: return None
	try:
		with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
			cursor.execute(sql, (item_url,))
			result = cursor.fetchone()
			return result['status'] if result else None
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to check acquisition log: {e}")
		return None
	finally:
		if conn: conn.close()


def log_acquisition(item_url, source_id, title, status, notes=""):
	"""Logs an item to the acquisition_log."""
	sql = """
          INSERT INTO acquisition_log (item_url, source_id, title, status, notes)
          VALUES (%s, %s, %s, %s, %s)
          ON CONFLICT (item_url) DO UPDATE SET status       = EXCLUDED.status,
                                               notes        = EXCLUDED.notes,
                                               process_date = CURRENT_TIMESTAMP; \
	      """
	conn = get_db_connection()
	if not conn: return
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (item_url, source_id, title, status, notes))
			conn.commit()
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to log acquisition: {e}")
		conn.rollback()
	finally:
		if conn: conn.close()


def update_source_check_time(source_id):
	"""Updates the last_checked_date for a source."""
	sql = "UPDATE sources SET last_checked_date = %s WHERE id = %s;"
	conn = get_db_connection()
	if not conn: return
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (datetime.now(), source_id))
			conn.commit()
	except Exception as e:
		print(f"[DB_MANAGER ERROR]: Failed to update source check time: {e}")
		conn.rollback()
	finally:
		if conn: conn.close()
