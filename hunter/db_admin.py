#  ==========================================================
#  Hunter's Command Console
#  #
#  File: db_admin.py
#  Last Modified: 8/17/25, 11:18 AM
#  #
#  Copyright (c) 2025, M. Stilson & Codex
#  #
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the MIT License.
#  #
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  LICENSE file for more details.
#  ==========================================================

import psycopg2
import psycopg2.extras
from hunter import config_manager
from hunter import db_manager

# --- Helper Function for Connections ---
def get_db_connection():
    try:
        db_creds = config_manager.get_pgsql_admin_credentials()
        if not db_creds:
            print("[DB_MANAGER ERROR]: PostgreSQL credentials not found.")
            return None

        db_creds['options'] = '-c search_path=almanac,public'
        conn = psycopg2.connect(**db_creds)
        return conn
    except Exception as e:
        print(f"[DB_MANAGER ERROR]: Could not connect to PostgreSQL: {e}")
        return None

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

def add_source(source_data):
    domain = db_manager.get_source_domain_by_name(source_data.get('domain_name'))
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

def add_keywords(keyword_data):
    """
    Adds a list of keywords to the keyword_library.
    keyword_data should be a list of tuples: [('keyword1', 'theme1'), ('keyword2', 'theme2')]
    """
    sql = "INSERT INTO keyword_library (keyword, theme) VALUES %s ON CONFLICT (keyword, theme) DO NOTHING;"
    conn = get_db_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            # Use executemany for efficient bulk inserting
            psycopg2.extras.execute_values(
                cursor, sql, keyword_data, template=None, page_size=100
            )
            conn.commit()
            print(f"[DB_ADMIN]: Successfully added/updated {len(keyword_data)} keywords.")
    except Exception as e:
        print(f"[DB_ADMIN ERROR]: Failed to add keywords: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()