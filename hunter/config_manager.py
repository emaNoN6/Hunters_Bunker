# hunter/config_manager.py

# ==========================================================
# Hunter's Command Console - Configuration Manager v2.0
# This definitive version loads the config file only once
# for improved performance and cleaner code.
# ==========================================================

import configparser
import os

# --- Configuration ---
# Define the path to the config file relative to this script's location.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")

# --- The "Single Load" Pattern ---
# We create a single, module-level config object.
_config = configparser.ConfigParser()
# We read the file right when this module is first imported.
_config.read(CONFIG_FILE)


# --- Default Creation Function ---
def create_default_config_if_needed():
    """If config.ini doesn't exist, create it with all necessary sections and default values."""
    if not os.path.exists(CONFIG_FILE):
        print("[CONFIG_MANAGER]: config.ini not found. Creating a default one.")

        default_config = configparser.ConfigParser()

        # Add all the sections we've planned for.
        default_config["Debug"] = {"debug_mode": "False"}
        default_config["GUI"] = {
            "font_family": "Courier New",
            "font_size": "14",
            "dark_bg": "#242424",
            "dark_gray": "#2b2b2b",
            "text_color": "#E0E0E0",
            "accent_color": "#A9D1F5",
        }
        default_config["General"] = {"balance_threshold": "0.95"}
        default_config["PostgreSQL"] = {
            "host": "localhost",
            "port": "5432",
            "dbname": "hunters_almanac",
            "user": "hunter_app_user",
            "password": "YOUR_PASSWORD_HERE",
        }
        default_config["GNewsIO"] = {"api_key": "YOUR_GNEWS.IO_API_KEY_HERE"}
        default_config["Reddit"] = {
            "client_id": "YOUR_REDDIT_CLIENT_ID",
            "client_secret": "YOUR_REDDIT_CLIENT_SECRET",
            "user_agent": "hunters_console/v0.1 by your_username",
        }

        with open(CONFIG_FILE, "w") as configfile:
            default_config.write(configfile)

        # After creating, we need to re-read it into our main config object.
        _config.read(CONFIG_FILE)


# --- Getter Functions ---
# All these functions are now lightning fast because they just read
# from the _config object that's already in memory.


def is_debug_mode():
    """Check if the application is running in debug mode."""
    is_debug_mode = _config.getboolean("Debug", "debug_mode", fallback=False)
    print(f"[CONFIG_MANAGER]: Debug mode is {'enabled' if is_debug_mode else 'disabled'}.")
    return is_debug_mode


def get_gui_config():
    """Reads the GUI configuration settings."""
    if "GUI" in _config:
        return dict(_config["GUI"])
    return {}


def get_general_config():
    """Reads the general configuration settings."""
    if "General" in _config:
        return dict(_config["General"])
    return {}


def get_pgsql_credentials():
    """Reads the PostgreSQL credentials."""
    if "PostgreSQL" in _config:
        return dict(_config["PostgreSQL"])
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
        # Check if the values are placeholders
        if "YOUR_" in creds.get("client_id", "") or "YOUR_" in creds.get(
            "client_secret", ""
        ):
            return None
        return creds
    return None


# --- Initial Setup ---
# Run the check to create the default config when this module is first loaded.
create_default_config_if_needed()
