# ==========================================================
# Hunter's Command Console - Configuration Manager v4.0
# This version consolidates all credential handling into one
# file for simplicity, reading from config.ini + .env
# ==========================================================

import configparser
import os
import sys
from hunter.utils import path_utils
from dotenv import load_dotenv

# --- Load environment variables FIRST ---
load_dotenv()

# --- Configuration ---
CONFIG_FILE = os.path.join(path_utils.get_project_root(), "config.ini")

# --- The "Single Load" Pattern ---
_config = configparser.ConfigParser()


def _load_config():
	"""Loads the config file or exits if it's not found."""
	if not os.path.exists(CONFIG_FILE):
		print(f"[CONFIG_MANAGER FATAL]: config.ini not found at: {CONFIG_FILE}")
		sys.exit(1)
	_config.read(CONFIG_FILE)
	print("[CONFIG_MANAGER]: Configuration loaded successfully.")


# --- Getter Functions ---

def is_debug_mode():
	"""Check if the application is running in debug mode."""
	return _config.getboolean("Debug", "debug_mode", fallback=False)


def get_gui_config():
	"""Reads the GUI configuration settings."""
	return dict(_config["GUI"]) if "GUI" in _config else {}


def get_pgsql_credentials():
	"""Reads the low-privilege PostgreSQL credentials from config.ini + .env"""
	if "PostgreSQL" in _config:
		creds = dict(_config["PostgreSQL"])
		# Override password from .env
		creds['user'] = os.getenv('DB_USER')
		creds['password'] = os.getenv('DB_PASSWORD')
		return creds
	return None


def get_pgsql_admin_credentials():
	"""Reads the high-privilege PostgreSQL ADMIN credentials from config.ini + .env"""
	if "PostgreSQL_Admin" in _config:
		creds = dict(_config["PostgreSQL_Admin"])
		# Override password from .env
		creds['user'] = os.getenv('DB_ADMIN_USER')
		creds['password'] = os.getenv('DB_ADMIN_PASSWORD')
		return creds
	else:
		print("[CONFIG_MANAGER WARNING]: [PostgreSQL_Admin] section not found in config.ini")
		return None


def get_db_connection_string():
	"""
	Constructs a libpq connection string from the PostgreSQL credentials.
	Format: postgresql://user:password@host:port/dbname
	"""
	creds = get_pgsql_credentials()
	if not creds:
		return None

	# Standard libpq connection string construction
	return f"postgresql://{creds['user']}:{creds['password']}@{creds['host']}:{creds['port']}/{creds['dbname']}"


def get_logging_config():
	"""Reads the [Logging] section from the config file."""
	if not _config:
		_load_config()
	if 'Logging' in _config:
		return dict(_config['Logging'])
	return {}


def get_gnews_io_credentials():
	"""Reads the GNews.io credentials from .env"""
	api_key = os.getenv('GNEWS_API_KEY')
	if api_key:
		return {'api_key': api_key}
	return None


def get_reddit_credentials():
	"""Reads the Reddit credentials from .env + config.ini"""
	client_id = os.getenv('REDDIT_CLIENT_ID')
	client_secret = os.getenv('REDDIT_CLIENT_SECRET')
	user_agent = os.getenv('REDDIT_USER_AGENT')

	if client_id and client_secret:
		return {
			'client_id':     client_id,
			'client_secret': client_secret,
			'user_agent':    user_agent
		}
	return None


def get_wordsapi_credentials():
	"""Reads the WordsAPI credentials from .env"""
	api_key = os.getenv('WORDSAPI_KEY')
	api_host = os.getenv('WORDSAPI_HOST')

	if api_key and api_host:
		return {
			'api_key':  api_key,
			'api_host': api_host
		}
	return None


# --- Initial Setup ---
_load_config()