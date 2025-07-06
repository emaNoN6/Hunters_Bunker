-- Hunter's Almanac: Database Schema
-- This file defines the complete database structure.

-- The main archive for confirmed case files.
CREATE TABLE IF NOT EXISTS "cases" (
    "id"	INTEGER,
    "public_uuid"	TEXT NOT NULL UNIQUE,
    "title"	TEXT NOT NULL,
    "url"	TEXT NOT NULL UNIQUE,
    "source_name"	TEXT,
    "full_text"	TEXT,
    "full_html"	TEXT,
    "search_vector"	TEXT,
    "status"	TEXT DEFAULT 'New',
    "triage_date"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    "category"	TEXT,
    PRIMARY KEY("id" AUTOINCREMENT)
);

-- Dynamically manages all our intelligence gathering agents.
CREATE TABLE IF NOT EXISTS "sources" (
    "id"	INTEGER,
    "source_name"	TEXT NOT NULL UNIQUE,
    "source_type"	TEXT NOT NULL,
    "target"	TEXT NOT NULL,
    "strategy"	TEXT,
    "keywords"	TEXT,
    "is_active"	INTEGER NOT NULL DEFAULT 1,
    "purpose"	TEXT NOT NULL DEFAULT 'lead_generation',
    "last_checked_date"	TIMESTAMP,
    "next_release_date"	TIMESTAMP,
    "last_known_item_id"	TEXT,
    PRIMARY KEY("id" AUTOINCREMENT)
);

-- The master journal for all items ever encountered to prevent re-processing.
CREATE TABLE IF NOT EXISTS "acquisition_log" (
    "item_url"	TEXT,
    "source_id"	INTEGER NOT NULL,
    "title"	TEXT,
    "status"	TEXT NOT NULL CHECK(status IN ('PROCESSED', 'IGNORED', 'FAILED')),
    "notes"	TEXT,
    "process_date"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY("item_url")
);

-- "Birth certificate" for our trained AI models to track staleness.
CREATE TABLE IF NOT EXISTS "model_metadata" (
    "model_name"	TEXT,
    "train_date"	TIMESTAMP NOT NULL,
    "case_word_count"	INTEGER NOT NULL,
    "not_case_word_count"	INTEGER NOT NULL,
    "categories"	TEXT NOT NULL,
    PRIMARY KEY("model_name")
);

-- Stores metadata for all non-textual evidence (images, audio, etc.).
CREATE TABLE IF NOT EXISTS "media_evidence" (
    "id"	INTEGER,
    "public_uuid"	TEXT NOT NULL UNIQUE,
    "case_id"	INTEGER NOT NULL,
    "location"	TEXT NOT NULL UNIQUE,
    "location_type"	TEXT NOT NULL CHECK(location_type IN ('LOCAL', 'REMOTE', 'ARCHIVED')),
    "thumbnail_path"	TEXT,
    "description"	TEXT,
    "evidence_type"	TEXT,
    PRIMARY KEY("id" AUTOINCREMENT)
);

-- Stores the state of the hunter's workspace (the "cork board").
CREATE TABLE IF NOT EXISTS "investigations" (
	"id"	INTEGER,
    "public_uuid"	TEXT NOT NULL UNIQUE,
	"name"	TEXT NOT NULL,
	"status"	TEXT NOT NULL CHECK(status IN ('ACTIVE', 'ARCHIVED', 'COLD_CASE')),
	"summary"	TEXT,
	"version"	INTEGER NOT NULL DEFAULT 1,
	"parent_version_id"	INTEGER,
	"created_date"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	"modified_date"	TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
	PRIMARY KEY("id" AUTOINCREMENT)
);

-- Stores the "pushpins" on a specific investigation board.
CREATE TABLE IF NOT EXISTS "investigation_nodes" (
	"id"	INTEGER,
	"investigation_id"	INTEGER NOT NULL,
	"node_type"	TEXT NOT NULL CHECK(node_type IN ('CASE', 'MEDIA', 'NOTE')),
	"node_id"	INTEGER,
	"pos_x"	INTEGER DEFAULT 0,
	"pos_y"	INTEGER DEFAULT 0,
	"note_text"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);

-- Stores the "red string" connecting the pushpins.
CREATE TABLE IF NOT EXISTS "investigation_links" (
	"id"	INTEGER,
	"investigation_id"	INTEGER NOT NULL,
	"node_a_id"	INTEGER NOT NULL,
	"node_b_id"	INTEGER NOT NULL,
	"description"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
);

-- Stores the application's startup tasks and maintenance checklist.
CREATE TABLE IF NOT EXISTS "system_tasks" (
	"task_name"	TEXT,
	"status"	TEXT NOT NULL CHECK(status IN ('PENDING', 'IN_PROGRESS', 'COMPLETE')),
	"last_run_date"	TIMESTAMP,
	"notes"	TEXT,
	PRIMARY KEY("task_name")
);

