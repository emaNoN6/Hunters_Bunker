# ==========================================================
# Hunter's Command Console - Database Manager v3.0
# This version implements a professional, versioned
# database migration system.
# ==========================================================

import sqlite3
import os
import uuid

# --- Configuration ---
DB_FILE = "Hunters_Almanac.db"
MIGRATIONS_DIR = "migrations"  # The folder for our SQL blueprints
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_FILE)
MIGRATIONS_PATH = os.path.join(BASE_DIR, MIGRATIONS_DIR)

# --- Helper Function for Connections ---


def get_db_connection():
    """A simple helper to create and return a database connection."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Could not connect to database at {DB_PATH}: {e}")
        return None


# --- Migration Engine ---


def get_db_version(cursor):
    """Gets the current version of the database schema."""
    cursor.execute("PRAGMA user_version;")
    return cursor.fetchone()[0]


def set_db_version(cursor, version):
    """Sets the database schema version."""
    # PRAGMA commands don't support parameter substitution, so we format carefully.
    cursor.execute(f"PRAGMA user_version = {version};")


def run_migrations(status_callback=None):
    """
    The master ritual to check the database version and apply all
    necessary migration scripts in order.
    """
    if status_callback:
        status_callback("Initializing database...")

    os.makedirs(MIGRATIONS_PATH, exist_ok=True)

    conn = get_db_connection()
    if not conn:
        if status_callback:
            status_callback("FATAL: Database connection failed.")
        return

    try:
        cursor = conn.cursor()

        # Begin a transaction. If any migration fails, the whole thing rolls back.
        cursor.execute("BEGIN TRANSACTION;")

        current_version = get_db_version(cursor)
        if status_callback:
            status_callback(
                f"Current DB version: {current_version}. Checking for migrations..."
            )

        print(f"[DB MIGRATOR]: Current DB version: {current_version}")

        # Find all migration files and sort them numerically
        migration_files = sorted(
            [
                f
                for f in os.listdir(MIGRATIONS_PATH)
                if f.endswith(".sql") and f.split("_")[0].isdigit()
            ]
        )

        for filename in migration_files:
            migration_version = int(filename.split("_")[0])

            if migration_version > current_version:
                print(f"[DB MIGRATOR]: Applying migration {filename}...")
                if status_callback:
                    status_callback(f"Applying migration {migration_version}...")

                filepath = os.path.join(MIGRATIONS_PATH, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    sql_script = f.read()

                cursor.executescript(sql_script)
                set_db_version(cursor, migration_version)
                conn.commit()  # Commit after each successful migration
                current_version = migration_version  # Update our tracker
                print(
                    f"[DB MIGRATOR]: Successfully applied version {migration_version}."
                )

        # Final commit for the whole transaction if all went well.
        conn.commit()
        if status_callback:
            status_callback("Database is up to date.")
        print("[DB MIGRATOR]: All migrations applied. Database is up to date.")

    except Exception as e:
        print(f"[DB MIGRATOR ERROR]: A fatal error occurred during migration: {e}")
        if status_callback:
            status_callback(f"ERROR: Migration failed: {e}")
        conn.rollback()  # Roll back any failed changes
    finally:
        if conn:
            conn.close()


# --- Case Management Functions (Example) ---
# We keep these separate from the migration logic.


def add_case(lead_data):
    """Adds a confirmed lead to the 'cases' table."""
    conn = get_db_connection()
    if not conn:
        return None
    # ... (rest of the function is the same as before) ...
    # This is where all our other functions like add_source, get_cases etc. will live.


# --- Main Execution Block for Testing ---
if __name__ == "__main__":
    print("Running DB Manager directly for setup and testing...")

    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed old database file for a clean test: {DB_FILE}")

    run_migrations()

    # You can add test calls to other functions here
    print("\nDB Manager test complete.")
