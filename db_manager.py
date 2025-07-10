# ==========================================================
# Hunter's Command Console - Database Manager (PostgreSQL Edition)
# v2.0 - Fixes the UUID type adaptation error.
# ==========================================================

import psycopg2
import psycopg2.extras
import os
import uuid
import config_manager

# --- Helper Function for Connections ---


def get_db_connection():
    """
    Creates and returns a connection to the PostgreSQL database.
    It reads credentials from the config.ini file.
    """
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
    """
    A simple function to test if we can connect to the database.
    """
    conn = get_db_connection()
    if conn:
        print("[DB_MANAGER]: PostgreSQL connection successful.")
        conn.close()
        return True
    else:
        print("[DB_MANAGER]: PostgreSQL connection failed.")
        return False


# --- Case Management Functions ---


def add_case(lead_data):
    """
    Adds a confirmed lead to the 'cases' table in PostgreSQL.
    """
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

    # --- THE FIX IS HERE ---
    # We convert the UUID object to a string before sending it.
    # PostgreSQL's UUID column is smart enough to parse this string correctly.
    new_uuid = str(uuid.uuid4())
    case_id = None

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cursor:
            cursor.execute(
                sql,
                (
                    new_uuid,  # Now passing a simple string
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


# --- Main Execution Block for Testing ---
if __name__ == "__main__":
    print("Running DB Manager directly for testing...")

    if check_database_connection():
        print("\n--- Testing add_case function ---")
        test_lead = {
            "title": "PG Test Case: River Serpent Sighting",
            "url": "http://test.local/case/pg123",
            "source": "PG Test Data",
            "text": "A new serpent sighting has been reported.",
            "html": "<p>A new serpent sighting has been reported.</p>",
        }

        # Clean out the old test case for a clean run
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM cases WHERE url = %s", (test_lead["url"],))
            conn.commit()
            conn.close()

        new_case_id = add_case(test_lead)
        if new_case_id:
            print(f"Test case added/found successfully with ID: {new_case_id}")

        print("\n--- Testing duplicate prevention ---")
        add_case(test_lead)

    print("\nDB Manager test complete.")
