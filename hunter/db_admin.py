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
import logging
logger = logging.getLogger(__name__)

# --- Helper Function for Connections ---
def get_db_connection():
    try:
        db_creds = config_manager.get_pgsql_admin_credentials()
        if not db_creds:
            logger.error("[DB_MANAGER ERROR]: PostgreSQL credentials not found.")
            return None

        db_creds['options'] = '-c search_path=almanac,public'
        conn = psycopg2.connect(**db_creds)
        return conn
    except Exception as e:
        logger.error(f"[DB_MANAGER ERROR]: Could not connect to PostgreSQL: {e}")
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
        logger.error(f"[DB_MANAGER ERROR]: Failed to add source domain: {e}")
        conn.rollback()
    finally:
        if conn: conn.close()

def add_source(source_data):
    domain = db_manager.get_source_domain_by_name(source_data.get('domain_name'))
    if not domain:
        logger.error(f"[DB_MANAGER ERROR]: Domain '{source_data.get('domain_name')}' not found.")
        return
    sql = "INSERT INTO sources (source_name, target, domain_id, purpose) VALUES (%s, %s, %s, %s) ON CONFLICT (source_name) DO NOTHING;"
    conn = get_db_connection()
    if not conn: return
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql, (source_data['source_name'], source_data['target'], domain['id'],
                                 source_data.get('purpose', 'lead_generation')))
            conn.commit()
            logger.info(f"[DB_MANAGER]: Added/updated source '{source_data['source_name']}'.")
    except Exception as e:
        logger.error(f"[DB_MANAGER ERROR]: Failed to add source: {e}")
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
            logger.info(f"[DB_ADMIN]: Successfully added/updated {len(keyword_data)} keywords.")
    except Exception as e:
        logger.error(f"[DB_ADMIN ERROR]: Failed to add keywords: {e}")
        conn.rollback()
    finally:
        if conn:
            conn.close()


# ==========================================================
# Search Term Morphology & API Caching (WRITE Operations)
# ==========================================================

def store_search_term(base_term, api_response):
	"""
	Stores a search term with its full API response.

	Args:
		base_term (str): The base word
		api_response (dict): The full JSON response from WordsAPI

	Returns:
		bool: True on success, False on failure
	"""
	sql = """
		INSERT INTO search_terms (base_term, api_response, last_updated)
		VALUES (%s, %s, now())
		ON CONFLICT (base_term) DO UPDATE 
		SET api_response = EXCLUDED.api_response, last_updated = now();
	"""
	conn = get_db_connection()
	if not conn:
		return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (base_term, psycopg2.extras.Json(api_response)))
			conn.commit()
			return True
	except Exception as e:
		logger.error(f"[DB_ADMIN ERROR]: Failed to store search term '{base_term}': {e}")
		conn.rollback()
		return False
	finally:
		if conn:
			conn.close()


def store_derivation(base_term, derivation, source='wordsapi'):
	"""
	Stores a derivation/variant of a base term.

	Args:
		base_term (str): The base word
		derivation (str): The variant form
		source (str): Where this came from ('wordsapi' or 'inflect')

	Returns:
		bool: True on success, False on failure
	"""
	sql = """
		INSERT INTO search_derivations (base_term, derivation, source)
		VALUES (%s, %s, %s)
		ON CONFLICT (base_term, derivation) DO NOTHING;
	"""
	conn = get_db_connection()
	if not conn:
		return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (base_term, derivation, source))
			conn.commit()
			return True
	except Exception as e:
		logger.error(f"[DB_ADMIN ERROR]: Failed to store derivation '{derivation}' for '{base_term}': {e}")
		conn.rollback()
		return False
	finally:
		if conn:
			conn.close()


def store_synonym(base_term, synonym, sense_index, definition_snippet=None):
	"""
	Stores a synonym relationship with its context.

	Args:
		base_term (str): The base word
		synonym (str): The synonym
		sense_index (int): Which sense/definition this came from (0-indexed)
		definition_snippet (str, optional): Brief definition for context

	Returns:
		bool: True on success, False on failure
	"""
	sql = """
		INSERT INTO search_synonyms (base_term, synonym, sense_index, definition_snippet)
		VALUES (%s, %s, %s, %s)
		ON CONFLICT (base_term, synonym, sense_index) DO NOTHING;
	"""
	conn = get_db_connection()
	if not conn:
		return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (base_term, synonym, sense_index, definition_snippet))
			conn.commit()
			return True
	except Exception as e:
		logger.error(f"[DB_ADMIN ERROR]: Failed to store synonym '{synonym}' for '{base_term}': {e}")
		conn.rollback()
		return False
	finally:
		if conn:
			conn.close()


def log_api_call(service, endpoint, word_queried, response_code, response_headers):
	"""
	Logs an API call with rate limit information.

	Args:
		service (str): API service name (e.g., 'wordsapi')
		endpoint (str): The endpoint called (e.g., '/words/demon')
		word_queried (str): The word that was looked up
		response_code (int): HTTP response code
		response_headers (dict): Response headers containing rate limit info

	Returns:
		bool: True on success, False on failure
	"""
	sql = """
		INSERT INTO api_usage_log 
		(service, endpoint, word_queried, response_code, rate_limit_remaining, rate_limit_limit, rate_limit_reset)
		VALUES (%s, %s, %s, %s, %s, %s, %s);
	"""
	conn = get_db_connection()
	if not conn:
		return False
	try:
		with conn.cursor() as cursor:
			cursor.execute(sql, (
				service,
				endpoint,
				word_queried,
				response_code,
				response_headers.get('x-ratelimit-requests-remaining'),
				response_headers.get('x-ratelimit-requests-limit'),
				response_headers.get('x-ratelimit-requests-reset')
			))
			conn.commit()
			return True
	except Exception as e:
		logger.error(f"[DB_ADMIN ERROR]: Failed to log API call: {e}")
		conn.rollback()
		return False
	finally:
		if conn:
			conn.close()
