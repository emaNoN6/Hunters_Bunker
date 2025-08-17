-- ===== new beginning =====
-- Kick out any connected sessions first (important if you have psql or apps connected)
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = 'Hunters_Almanac'
  AND pid <> pg_backend_pid();

DROP DATABASE IF EXISTS "Hunters_Almanac";
CREATE DATABASE "Hunters_Almanac"
    WITH OWNER = hunter_admin
    ENCODING 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

ALTER DATABASE "Hunters_Almanac" OWNER TO hunter_admin;

-- == SWITCH TO Hunters_Almanac BEFORE RUNNING THESE ==
\c Hunters_Almanac
CREATE SCHEMA IF NOT EXISTS partman;
GRANT ALL ON SCHEMA partman TO hunter_admin;
CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
GRANT ALL ON ALL TABLES IN SCHEMA partman TO hunter_admin;
CREATE EXTENSION IF NOT EXISTS pg_cron;
GRANT ALL ON SCHEMA cron TO hunter_admin;
GRANT ALL ON ALL TABLES IN SCHEMA cron TO hunter_admin;
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;