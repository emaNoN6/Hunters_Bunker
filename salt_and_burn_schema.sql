-- Hunter's Almanac: PostgreSQL Schema v2.0
-- This version uses the modern, SQL-standard "GENERATED ALWAYS AS IDENTITY"
-- for all auto-incrementing primary keys.

-- The main archive for confirmed case files.
drop table if exists "cases";
CREATE TABLE IF NOT EXISTS "cases" (
    "id"	INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    "public_uuid"	UUID NOT NULL UNIQUE,
    "title"	TEXT NOT NULL,
    "url"	TEXT NOT NULL UNIQUE,
    "source_name"	TEXT,
    "full_text"	TEXT,
    "full_html"	TEXT,
    "search_vector"	TSVECTOR, -- PostgreSQL specific type for FTS
    "status"	TEXT DEFAULT 'New',
    "triage_date"	TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    "category"	TEXT
);

-- Dynamically manages all our intelligence gathering agents.
drop table if exists "sources";
CREATE TABLE IF NOT EXISTS "sources" (
    "id"	INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    "source_name"	TEXT NOT NULL UNIQUE,
    "source_type"	TEXT NOT NULL,
    "target"	TEXT NOT NULL,
    "strategy"	TEXT,
    "keywords"	TEXT,
    "is_active"	BOOLEAN NOT NULL DEFAULT TRUE,
    "purpose"	TEXT NOT NULL DEFAULT 'lead_generation',
    "last_checked_date"	TIMESTAMP WITH TIME ZONE,
    "next_release_date"	TIMESTAMP WITH TIME ZONE,
    "last_known_item_id"	TEXT
);

-- The master journal for all items ever encountered to prevent re-processing.
drop table if exists "acquisition_log";
CREATE TABLE IF NOT EXISTS "acquisition_log" (
    "item_url"	TEXT PRIMARY KEY,
    "source_id"	INTEGER NOT NULL,
    "title"	TEXT,
    "status"	TEXT NOT NULL CHECK(status IN ('PROCESSED', 'IGNORED', 'FAILED')),
    "notes"	TEXT,
    "process_date"	TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- "Birth certificate" for our trained AI models to track staleness.
drop table if exists "model_metadata";
CREATE TABLE IF NOT EXISTS "model_metadata" (
    "model_name"	TEXT PRIMARY KEY,
    "train_date"	TIMESTAMP WITH TIME ZONE NOT NULL,
    "case_word_count"	INTEGER NOT NULL,
    "not_case_word_count"	INTEGER NOT NULL,
    "categories"	TEXT NOT NULL
);

-- Stores metadata for all non-textual evidence (images, audio, etc.).
drop table if exists "media_evidence";
CREATE TABLE IF NOT EXISTS "media_evidence" (
    "id"	INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    "public_uuid"	UUID NOT NULL UNIQUE,
    "case_id"	INTEGER NOT NULL,
    "location"	TEXT NOT NULL UNIQUE,
    "location_type"	TEXT NOT NULL CHECK(location_type IN ('LOCAL', 'REMOTE', 'ARCHIVED')),
    "thumbnail_path"	TEXT,
    "description"	TEXT,
    "evidence_type"	TEXT
);

-- Stores the state of the hunter's workspace (the "cork board").
drop table if exists "investigations";
CREATE TABLE IF NOT EXISTS "investigations" (
	"id"	INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    "public_uuid"	UUID NOT NULL UNIQUE,
	"name"	TEXT NOT NULL,
	"status"	TEXT NOT NULL CHECK(status IN ('ACTIVE', 'ARCHIVED', 'COLD_CASE')),
	"summary"	TEXT,
	"version"	INTEGER NOT NULL DEFAULT 1,
	"parent_version_id"	INTEGER,
	"created_date"	TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
	"modified_date"	TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Stores the "pushpins" on a specific investigation board.
drop table if exists "investigation_nodes";
CREATE TABLE IF NOT EXISTS "investigation_nodes" (
	"id"	INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
	"investigation_id"	INTEGER NOT NULL,
	"node_type"	TEXT NOT NULL CHECK(node_type IN ('CASE', 'MEDIA', 'NOTE')),
	"node_id"	INTEGER,
	"pos_x"	INTEGER DEFAULT 0,
	"pos_y"	INTEGER DEFAULT 0,
	"note_text"	TEXT
);

-- Stores the "red string" connecting the pushpins.
drop table if exists "investigation_links";
CREATE TABLE IF NOT EXISTS "investigation_links" (
	"id"	INTEGER PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
	"investigation_id"	INTEGER NOT NULL,
	"node_a_id"	INTEGER NOT NULL,
	"node_b_id"	INTEGER NOT NULL,
	"description"	TEXT
);

-- Stores the application's startup tasks and maintenance checklist.
drop table if exists "system_tasks";
CREATE TABLE IF NOT EXISTS "system_tasks" (
	"task_name"	TEXT PRIMARY KEY,
	"status"	TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETE')),
	"last_run_date"	TIMESTAMP WITH TIME ZONE,
	"notes"	TEXT
);
