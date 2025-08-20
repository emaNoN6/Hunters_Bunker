Hunter's Command Console — Development Guidelines

Audience: Advanced developers working on this repository. The notes below are project-specific. They assume familiarity with Python packaging, PostgreSQL, and Windows PowerShell.

1) Build and Configuration
- Python/OS
  - Target platform: Windows (PowerShell commands below use backslashes).
  - Recommended: Python 3.11.x (other 3.10–3.12 versions may work given dependency pins).
- Environment Setup
  - Create a virtual environment and install dependencies:
    - py -3.11 -m venv .venv
    - .venv\Scripts\Activate
    - python -m pip install --upgrade pip
    - pip install -r requirements.txt
  - Heavy/optional deps: torch and openai-whisper are included for other subsystems but are not required to run basic GUI or tests in this document.
- Configuration: config.ini
  - Location: project root (C:\...\Hunters_Bunker\config.ini). The config_manager loads this file on import and will terminate the process (sys.exit) if missing.
  - Sections: [Debug], [General], [GUI], [GNewsIO], [Reddit], [PostgreSQL], [PostgreSQL_Admin]. Populate values per your environment. Debug configuration is read via config_manager.is_debug_mode().
  - Important: Importing hunter.config_manager will attempt to read config.ini immediately.
- Database (PostgreSQL)
  - Requirements: A running PostgreSQL instance (locally on 127.0.0.1:5432 by default). Create the database and two roles that match config.ini:
    - Database: Hunters_Almanac
    - User (app): hunter_app_user (least privilege)
    - User (admin): hunter_admin (high privilege for migrations)
  - Connection search_path: db_manager sets connection options to -c search_path=almanac,public. Schema almanac is created by the initial migration.
  - Extensions: The first migration (migrations\001_initial_schema.sql) contains commented extension statements (pgcrypto, pg_trgm, postgis, pg_partman). Enable them only if your server supports them and your admin role has privileges.
- DB Migrations Workflow
  - Run migrations using admin credentials from config.ini:
    - python tools\run_migrations.py
  - This uses hunter.admin.migration_manager:
    - Creates/ensures schema_version table
    - Applies migrations in ascending order (e.g., 001_*.sql)
  - Application preflight: python -m hunter triggers db_manager.verify_db_version() before launching the GUI. If DB is unreachable or out-of-date, the app prints a fatal message and does not start.

2) Testing
- Test Runner
  - This repo does not require pytest; use the standard library unittest.
  - Run a single test file:
    - python -m unittest tests\test_utils.py -v
  - Discover all tests under tests directory (pattern test_*.py):
    - python -m unittest discover -s tests -p "test_*.py" -v
- Writing Tests
  - Prefer tests that avoid side effects (DB, network, GUI). Favor pure functions from modules like hunter.utils.
  - Beware: Importing hunter.config_manager reads config.ini immediately and will exit if the file is missing. In tests that need config_manager, ensure config.ini exists or patch around it. For DB-related code, patch hunter.db_manager.get_db_connection to a fake/stub to avoid real DB connections.
  - Example patch (sketch):
    - from unittest.mock import patch
    - @patch('hunter.db_manager.get_db_connection', return_value=FakeConn())
- Verified Example Test (we ran this locally)
  - File created temporarily: tests\test_utils.py
  - Contents:
    - import unittest; import queue; import time; from hunter import utils
    - Start the background consumer with utils.start_console_log_consumer
    - Assert the thread is alive and daemonized; send a log message
  - Observed output when running python -m unittest tests\test_utils.py -v:
    - test_start_console_log_consumer_returns_daemon_thread ... [TEST] hello
    - ok
    - Ran 1 test in 0.201s
    - OK
  - We removed the temporary test file after verification as per this guideline’s housekeeping requirement. You can recreate it from the snippet above when needed.
- Adding New Tests
  - Create files under tests named test_*.py.
  - Use unittest.TestCase. Keep tests hermetic:
    - Avoid importing hunter.config_manager unless necessary.
    - For DB interactions, mock get_db_connection and avoid hitting a live DB.
    - For GUI code, prefer testing logic helpers rather than widget rendering.

3) Additional Development Notes
- Launching the Application
  - From project root: python -m hunter
  - Pre-flight DB check runs before GUI creation. If it fails, read the console message and run tools\run_migrations.py or fix DB connectivity.
- Agents and API Keys
  - GNews and Reddit credentials are read from config.ini (sections [GNewsIO], [Reddit]). The app may skip features if credentials are absent. Do not hardcode secrets in code.
- Code Style and Conventions
  - Python 3 style, 4-space indent, snake_case for functions/variables. Existing modules use relative imports within the hunter package.
  - Logging inside the GUI uses a queue feeding a log textbox; for background/non-GUI code, prefer lightweight print-based logging consistent with current modules or consider centralizing later.
- Database Layer Practices
  - db_manager registers uuid handling with psycopg2.extras.register_uuid() and sets search_path automatically.
  - verify_db_version() expects schema_version to exist; migrations ensure creation and versioning. New migrations should follow the NNN_description.sql pattern and be idempotent where practical.
- Common Pitfalls
  - Missing config.ini: hunter.config_manager will exit the process on import. Keep config.ini in the project root during development and tests.
  - DB connection failures: check host (127.0.0.1), port (5432), users/passwords, and that the almanac schema exists or that you have run the migrations.
  - Heavy dependencies: Installing torch/whisper can be slow. They aren’t required for unit tests shown here.
- Tools and Utilities
  - tools\run_migrations.py: Admin migration runner
  - tools\db_backup.py: Uses app credentials; ensure config.ini present
  - tools\bootstrap_case_data.py and tools\case_seeder.py: Rely on credentials and DB; prefer running after migrations

Housekeeping for This Document
- All steps and the example test were executed and verified before writing this file.
- Any temporary files created during demonstration were removed; this repository should only contain this guidance addition under .junie\guidelines.md as part of this change.
