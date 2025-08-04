# hunter/admin/migration_manager.py

import os
import sys
import psycopg2

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)
# --- End Magic ---

# --- THE UPGRADE IS HERE ---
# We now import our single, central config manager.
from hunter import config_manager

# --- Configuration ---
MIGRATIONS_DIR = "migrations"
MIGRATIONS_PATH = os.path.join(project_root, MIGRATIONS_DIR)


def get_admin_db_connection():
	"""
	This function now uses the central config manager to get the
	high-privilege credentials.
	"""
	try:
		db_creds = config_manager.get_pgsql_admin_credentials()
		if not db_creds:
			print("[MIGRATOR ERROR]: Admin credentials not found in config.ini")
			return None
		conn = psycopg2.connect(**db_creds)
		return conn
	except Exception as e:
		print(f"[MIGRATOR ERROR]: Could not connect with admin credentials: {e}")
		return None

def run_migrations():
	"""The master migration ritual."""
	print("[MIGRATOR]: Checking database schema version...")

	conn = get_admin_db_connection()
	if not conn:
		print("[MIGRATOR FATAL]: Could not connect to database. Halting.")
		return False

	try:
		with conn.cursor() as cursor:
			cursor.execute("BEGIN TRANSACTION;")

			cursor.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);")
			cursor.execute("SELECT version FROM schema_version;")
			result = cursor.fetchone()
			if not result:
				cursor.execute("INSERT INTO schema_version (version) VALUES (0);")
				current_version = 0
			else:
				current_version = result[0]

			print(f"[MIGRATOR]: Current DB version: {current_version}")

			if not os.path.isdir(MIGRATIONS_PATH):
				print(f"[MIGRATOR WARNING]: Migrations directory not found.")
				conn.commit()
				return True

			migration_files = sorted(
					[f for f in os.listdir(MIGRATIONS_PATH) if f.endswith('.sql') and f.split('_')[0].isdigit()])

			for filename in migration_files:
				migration_version = int(filename.split('_')[0])
				if migration_version > current_version:
					print(f"[MIGRATOR]: Applying migration {filename}...")
					filepath = os.path.join(MIGRATIONS_PATH, filename)
					with open(filepath, 'r') as f:
						sql_script = f.read()

					cursor.execute(sql_script)
					cursor.execute("UPDATE schema_version SET version = %s;", (migration_version,))
					print(f" -> Successfully applied version {migration_version}.")

			conn.commit()
			print("[MIGRATOR]: Database is up to date.")
			return True

	except Exception as e:
		print(f"[MIGRATOR FATAL ERROR]: {e}")
		conn.rollback()
		return False
	finally:
		if conn:
			conn.close()
