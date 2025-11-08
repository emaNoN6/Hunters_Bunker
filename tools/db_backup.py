#  ==========================================================
#  Hunter's Command Console
#  #
#  File: db_backup.py
#  Last Modified: 7/27/25, 2:57 PM
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

# tools/backup_db.py

import os
import sys
import subprocess
from datetime import datetime
import logging

# --- Pathing Magic ---
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)
# --- End Magic ---

from hunter import config_manager

# --- Configuration ---
BACKUP_DIR_NAME = "db_backups"
NUM_BACKUPS_TO_KEEP = 7
LOG_FILE_NAME = "db_backup.log"
# The name of your PostgreSQL Docker container
DOCKER_CONTAINER_NAME = "pgsql-container"

# This sets up a simple logger that writes to a file in the same directory as the script.
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), LOG_FILE_NAME)
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def run_backup():
    """
    Connects to the PostgreSQL Docker container and creates a backup
    using 'docker exec' to run the pg_dump utility inside the container.
    """
    logging.info("[BACKUP AGENT]: Beginning database backup operation...")

    # --- Get Credentials ---
    creds = config_manager.get_pgsql_admin_credentials()
    if not creds:
        logging.error(
            "[BACKUP ERROR]: Could not read PostgreSQL credentials from config.ini. Aborting."
        )
        return

    # --- Define Paths ---
    backup_dir = os.path.join(project_root, BACKUP_DIR_NAME)
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"hunters_almanac_backup_{timestamp}.sql"
    backup_filepath = os.path.join(backup_dir, backup_filename)

    # --- Build the 'docker exec' Command ---
    # This is the new, correct spell. We are telling Docker to run pg_dump
    # inside the container.
    command = [
        "docker",
        "exec",
        # Pass the password securely as an environment variable inside the container
        "-e",
        f"PGPASSWORD={creds['password']}",
        DOCKER_CONTAINER_NAME,
        "pg_dump",
        "-U",
        creds["user"],
        "-d",
        creds["dbname"],
        "--clean",
        "--if-exists",
	    "--exclude-schema=cron",
	    "--exclude-schema=partman",
	    "--exclude-schema=public",
    ]

    # --- Execute the Backup ---
    logging.info(f" -> Creating backup: {backup_filename}")
    try:
        # We run the command and capture its standard output.
        # pg_dump writes the backup data to stdout by default.
        process = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",  # Be explicit about encoding
        )

        # Now, we take the captured output and write it to our local file.
        with open(backup_filepath, "w", encoding="utf-8") as f:
            f.write(process.stdout)

        logging.info("[BACKUP SUCCESS]: Database backup created successfully.")
    except FileNotFoundError:
        logging.fatal(
            "[BACKUP FATAL ERROR]: 'docker' command not found. Is Docker Desktop running and in your PATH?"
        )
        return
    except subprocess.CalledProcessError as e:
        logging.fatal("[BACKUP FATAL ERROR]: docker exec or pg_dump failed.")
        logging.fatal(f" -> STDERR: {e.stderr}")
        return

    # --- Prune Old Backups (This logic is unchanged) ---
    logging.info(" -> Pruning old backups...")
    try:
        all_backups = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith(".sql")],
            key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
        )

        if len(all_backups) > NUM_BACKUPS_TO_KEEP:
            backups_to_delete = all_backups[:-NUM_BACKUPS_TO_KEEP]
            logging.info(f" -> Found {len(backups_to_delete)} old backup(s) to delete.")
            for filename in backups_to_delete:
                os.remove(os.path.join(backup_dir, filename))
                logging.info(f"   -> Deleted: {filename}")
        else:
            logging.info(" -> No old backups to prune.")

    except Exception as e:
        logging.error(f"[BACKUP WARNING]: Could not prune old backups: {e}")

    logging.info("[BACKUP AGENT]: Operation complete.")


if __name__ == "__main__":
    run_backup()
