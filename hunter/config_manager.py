# FILE 1: config_manager.py (WITH DEBUG LOGGING)
# ===============================================
# We've added print statements to see exactly what this file is reading.

import configparser
import os

import yaml

# Using the robust pathing from before
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# IMPORTANT: This assumes config.ini is in the MAIN project folder, one level UP from this file.
# If your config.ini is in the same folder as this script, remove the '..'
# Example: If config_manager.py is in 'Hunters_Bunker/', the path is correct.
# If config_manager.py is in 'Hunters_Bunker/some_subfolder/', the path is correct.
CONFIG_FILE = os.path.join(SCRIPT_DIR, "config.ini")


def create_default_config():
    """If config.ini doesn't exist, create it with default values."""
    if not os.path.exists(CONFIG_FILE):
        print("config.ini not found. Creating a default one.")
        config = configparser.ConfigParser()
        config["GNews"] = {"api_key": "YOUR_API_KEY_HERE"}
        config["Reddit"] = {
            "client_id": "YOUR_REDDIT_CLIENT_ID",
            "client_secret": "YOUR_REDDIT_CLIENT_SECRET",
            "user_agent": "hunters_console_v0.1_by_your_username",
        }
        with open(CONFIG_FILE, "w") as configfile:
            config.write(configfile)


def get_ignore_list():
    """
    Reads the ignore_list.yaml file and returns the parsed data.
    Returns an empty list if the file doesn't exist.
    """
    try:
        with open("ignore_list.yaml", "r") as f:
            ignore_data = yaml.safe_load(f)
            print("[CONFIG]: Successfully loaded ignore_list.yaml")
            return ignore_data if ignore_data is not None else []
    except FileNotFoundError:
        print("[CONFIG]: ignore_list.yaml not found. No rules will be applied.")
        return []
    except Exception as e:
        print(f"[CONFIG]: ERROR reading or parsing ignore_list.yaml: {e}")
        return []


def get_config_value(section, key):
    config = configparser.ConfigParser()
    files_read = config.read(CONFIG_FILE)
    if not files_read:
        # This debug line is critical
        print(
            f"[DEBUG] config_manager: FAILED to read config file at path: {os.path.abspath(CONFIG_FILE)}"
        )
        return None
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return None


def get_gnews_api_key():
    return get_config_value("GNews", "api_key")


def get_reddit_credentials():
    """
    This function now has heavy logging to see what it's doing.
    """
    print("[DEBUG] config_manager: Attempting to get Reddit credentials...")

    client_id = get_config_value("Reddit", "client_id")
    client_secret = get_config_value("Reddit", "client_secret")
    user_agent = get_config_value("Reddit", "user_agent")

    # Print exactly what we found (or didn't find)
    print(f"[DEBUG] config_manager: Found client_id: '{client_id}'")
    print(f"[DEBUG] config_manager: Found client_secret: '{client_secret}'")
    print(f"[DEBUG] config_manager: Found user_agent: '{user_agent}'")

    # Check if any of the values are None or the default placeholder
    if all(
        val and "YOUR_" not in val and val is not None
        for val in [client_id, client_secret, user_agent]
    ):
        creds = {
            "client_id": client_id,
            "client_secret": client_secret,
            "user_agent": user_agent,
        }
        print(
            "[DEBUG] config_manager: All Reddit keys found. Returning credentials dictionary."
        )
        return creds

    print(
        "[DEBUG] config_manager: One or more Reddit keys are missing or default. Returning empty dictionary."
    )
    return {}  # Return empty dict if not fully configured


def get_pgsql_credentials():
    """Reads the PostgreSQL credentials from the config.ini file."""
    config = configparser.ConfigParser()
    # Make sure CONFIG_PATH is defined at the top of your file
    config.read(CONFIG_FILE)

    if "PostgreSQL" in config:
        return dict(config["PostgreSQL"])
    else:
        return None
