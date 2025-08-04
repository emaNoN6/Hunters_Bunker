# ==========================================================
# Hunter's Command Console - Configuration Manager v4.0
# This version consolidates all credential handling into one
# file for simplicity, reading from a single config.ini.
# ==========================================================

import configparser
import os
import sys

# --- Configuration ---
# This uses your robust pathing to find config.ini in the project root.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "config.ini")

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
    """Reads the low-privilege PostgreSQL credentials."""
    return dict(_config["PostgreSQL"]) if "PostgreSQL" in _config else None

def get_pgsql_admin_credentials():
    """Reads the high-privilege PostgreSQL ADMIN credentials."""
    if "PostgreSQL_Admin" in _config:
        return dict(_config["PostgreSQL_Admin"])
    else:
        print("[CONFIG_MANAGER WARNING]: [PostgreSQL_Admin] section not found in config.ini")
        return None


def get_gnews_io_credentials():
    """Reads the GNews.io credentials."""
    if "GNewsIO" in _config:
        return dict(_config["GNewsIO"])
    return None


def get_reddit_credentials():
    """Reads the Reddit credentials."""
    if "Reddit" in _config:
        creds = dict(_config["Reddit"])
        if "YOUR_" in creds.get("client_id", ""): return None
        return creds
    return None

# ... (add other credential getters like gnews.io here as needed) ...

# --- Initial Setup ---
_load_config()
