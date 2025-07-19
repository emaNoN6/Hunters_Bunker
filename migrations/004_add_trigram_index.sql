-- =======================================================
-- Hunter's Almanac: Migration 004
-- This script installs the pg_trgm extension and adds a
-- GIN trigram index to the cases.title column. This enables
-- fast, efficient, and typo-tolerant "fuzzy" searching.
-- =======================================================

-- First, we cast the spell to activate the trigram magic for this database.
-- We use "IF NOT EXISTS" to make this script safe to re-run.
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Next, we create the GIN index on the 'title' column.
-- The 'gin_trgm_ops' tells PostgreSQL to use the special trigram
-- operator class, which is what enables the fuzzy matching.
CREATE INDEX cases_title_trgm_idx ON cases USING GIN (title gin_trgm_ops);

