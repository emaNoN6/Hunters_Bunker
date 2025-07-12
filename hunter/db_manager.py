# ==========================================================
# Hunter's Command Console - Database Manager (PostgreSQL Edition)
# v2.1 - Complete version with all functions implemented.
# ==========================================================

import psycopg2
import psycopg2.extras
import os
import uuid
from hunter import config_manager
from datetime import datetime

# --- Helper Function for Connections ---


def get_db_connection():
    """Creates and returns a connection to the PostgreSQL database."""
    try:
        db_creds = config_manager.get_pgsql_credentials()
        if not db_creds:
            print("[DB_MANAGER ERROR]: PostgreSQL credentials not found in config.ini")
            return None

        conn = psycopg2.connect(
            host=db_creds["host"],
            dbname=db_creds["dbname"],
            user=db_creds["user"],
            password=db_creds["password"],
            port=db_creds.get("port", 5432),
        )
        return conn
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Could not connect to PostgreSQL database: {e}")
        return None


# --- Setup Function (For Verification) ---


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


# --- Source Management Functions ---


def add_source(source_data):
    """Adds a new intelligence source to the database."""
    sql = """
    INSERT INTO sources (source_name, source_type, target, strategy, keywords, purpose)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_name) DO NOTHING;
    """
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                sql,
                (
                    source_data["source_name"],
                    source_data["source_type"],
                    source_data["target"],
                    source_data.get("strategy"),
                    source_data.get("keywords"),
                    source_data.get("purpose", "lead_generation"),
                ),
            )
            conn.commit()
            print(f"[DB_MANAGER]: Added/updated source '{source_data['source_name']}'.")
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Failed to add source: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


def get_active_lead_sources():
    """Retrieves all sources marked for lead generation."""
    sql = (
        "SELECT * FROM sources WHERE is_active = TRUE AND purpose = 'lead_generation';"
    )
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(sql)
            sources = cursor.fetchall()
            return [dict(row) for row in sources]
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Failed to get active sources: {e}")
        return []
    finally:
        if conn:
            conn.close()


def update_source_check_time(source_id):
    """Updates the last_checked_date for a source."""
    sql = "UPDATE sources SET last_checked_date = %s WHERE id = %s;"
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (datetime.now(), source_id))
            conn.commit()
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Failed to update source check time: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


# --- Acquisition Log Functions ---


def check_acquisition_log(item_url):
    """Checks if an item has already been processed or ignored."""
    sql = "SELECT status FROM acquisition_log WHERE item_url = %s;"
    conn = get_db_connection()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(sql, (item_url,))
            result = cursor.fetchone()
            return result["status"] if result else None
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Failed to check acquisition log: {e}")
        return None
    finally:
        if conn:
            conn.close()


def log_acquisition(item_url, source_id, title, status, notes=""):
    """Logs an item to the acquisition_log."""
    sql = """
    INSERT INTO acquisition_log (item_url, source_id, title, status, notes)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (item_url) DO UPDATE SET
        status = EXCLUDED.status,
        notes = EXCLUDED.notes,
        process_date = CURRENT_TIMESTAMP;
    """
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (item_url, source_id, title, status, notes))
            conn.commit()
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Failed to log acquisition: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


# --- Case Management Functions ---


def add_case(lead_data):
    """Adds a confirmed lead to the 'cases' table in PostgreSQL."""
    conn = get_db_connection()
    if not conn:
        return None

    if not lead_data.get("url"):
        print("[DB_MANAGER WARNING]: Attempted to add a case with no URL. Aborting.")
        return None

    sql = """
    INSERT INTO cases (public_uuid, title, url, source_name, full_text, full_html)
    VALUES (%s, %s, %s, %s, %s, %s)
    ON CONFLICT (url) DO NOTHING
    RETURNING id;
    """

    new_uuid = str(uuid.uuid4())
    case_id = None

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(
                sql,
                (
                    new_uuid,
                    lead_data.get("title", "No Title"),
                    lead_data.get("url"),
                    lead_data.get("source", "Unknown"),
                    lead_data.get("text", ""),
                    lead_data.get("html", ""),
                ),
            )

            result = cursor.fetchone()
            if result:
                case_id = result["id"]
                print(
                    f"[DB_MANAGER]: Successfully filed new case: {lead_data.get('title')}"
                )
            else:
                print(
                    f"[DB_MANAGER]: Case already exists in archive: {lead_data.get('title')}"
                )
                cursor.execute(
                    "SELECT id FROM cases WHERE url = %s", (lead_data.get("url"),)
                )
                existing_case = cursor.fetchone()
                if existing_case:
                    case_id = existing_case["id"]

            conn.commit()

    except Exception as e:
        print(f"[DB_MANAGER ERROR]: An error occurred adding a case: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()

    return case_id


def get_random_cases_for_testing(limit=20):
    """Fetches a random sample of cases from the database for testing."""
    sql = "SELECT * FROM cases WHERE full_html IS NOT NULL ORDER BY RANDOM() LIMIT %s;"
    conn = get_db_connection()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(sql, (limit,))
            cases = cursor.fetchall()
            # Convert the results to a list of standard dicts
            return [dict(row) for row in cases]
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Failed to get random cases: {e}")
        return []
    finally:
        if conn:
            conn.close()


# --- Main Execution Block for Testing ---
if __name__ == "__main__":
    print("Running DB Manager directly for testing...")

    if check_database_connection():
        # Add a test source to the database
        test_source = {
            "source_name": "Test Data Source",
            "source_type": "test_data",
            "target": "test_leads.json",
            "purpose": "lead_generation",
        }
        add_source(test_source)

        # Fetch and print the active sources
        active_sources = get_active_lead_sources()
        print(f"\nFound {len(active_sources)} active sources:")
        for source in active_sources:
            print(
                f"  - {source['source_name']} (ID: {source['id']}, Type: {source['source_type']})"
            )

        # Test the acquisition log
        test_url = "http://test.local/case/test001"
        print(f"\nChecking log for: {test_url}")
        status = check_acquisition_log(test_url)
        print(f"  -> Status: {status}")

        print(f"Logging item as 'PROCESSED'...")
        # Make sure we have a source to get an ID from
        if active_sources:
            log_acquisition(
                test_url, active_sources[0]["id"], "Test Lead 1", "PROCESSED"
            )
            status = check_acquisition_log(test_url)
            print(f"  -> New Status: {status}")
        else:
            print("  -> Skipping log test, no sources found.")

    print("\nDB Manager test complete.")
