/*
 * # ==========================================================
 * # Hunter's Command Console - Definitive Initial Schema (Schema-Agnostic)
 * #
 * # Description: This script creates a complete, testable database
 * # schema. It is designed to run within any dedicated schema
 * # (e.g., 'testing') without hardcoding names, making it portable.
 * # It incorporates all migrations and best practices.
 * # Now integrates pg_partman for automated partition management.
 * # ==========================================================
 */

-- === 0. SANDBOX SETUP ===
-- uncomment to create a sandbox schema for testing
CREATE SCHEMA IF NOT EXISTS almanac;
SET search_path = almanac, public;

-- === 1. EXTENSIONS ===
-- === THESE MUST BE RUN AS SUPERUSER ===
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- CREATE EXTENSION IF NOT EXISTS pg_trgm;
-- CREATE EXTENSION IF NOT EXISTS postgis;
-- CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman;
-- partition management

-- === 2. CORE ENUMERATED TYPES ===
DO
$$
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'case_status') THEN
            CREATE TYPE case_status AS ENUM ('NEW', 'TRIAGED', 'ACTIVE', 'CLOSED');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'investigation_status') THEN
            CREATE TYPE investigation_status AS ENUM ('ACTIVE', 'PAUSED', 'ARCHIVED', 'COLD_CASE');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'acquisition_status') THEN
            CREATE TYPE acquisition_status AS ENUM ('NEW', 'PROCESSED', 'SKIPPED', 'ERROR', 'IGNORED');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'media_location_type') THEN
            CREATE TYPE media_location_type AS ENUM ('LOCAL', 'REMOTE', 'ARCHIVED');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'node_type') THEN
            CREATE TYPE node_type AS ENUM ('CASE', 'MEDIA', 'NOTE');
        END IF;
    END
$$;

-- === 3. FUNCTIONS & TRIGGERS ===

CREATE OR REPLACE FUNCTION touch_modified()
    RETURNS TRIGGER AS
$$
BEGIN
    NEW.modified_date = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Note: join on composite key to avoid ambiguity across partitions
CREATE OR REPLACE FUNCTION cases_tsvector_update()
    RETURNS TRIGGER AS
$$
DECLARE
    case_title TEXT;
BEGIN
    SELECT title
    INTO case_title
    FROM cases
    WHERE id = NEW.case_id
      AND publication_date = NEW.publication_date;

    NEW.search_vector :=
            setweight(to_tsvector('english', coalesce(case_title, '')), 'A')
                || setweight(to_tsvector('english', coalesce(NEW.full_text, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_nearby_cases(lat double precision, lon double precision, radius_meters double precision)
    RETURNS TABLE
            (
                id              bigint,
                title           text,
                distance_meters double precision
            )
AS
$$
BEGIN
    RETURN QUERY
        SELECT c.id,
               c.title,
               ST_Distance(c.location_geom::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) AS distance
        FROM cases c
        WHERE c.location_geom IS NOT NULL
          AND ST_DWithin(c.location_geom::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography, radius_meters)
        ORDER BY distance;
END;
$$ LANGUAGE plpgsql;

-- Keep acquisition_router.partition_month aligned with last_seen_at
CREATE OR REPLACE FUNCTION update_router_partition_month()
    RETURNS trigger AS
$$
BEGIN
    NEW.partition_month := date_trunc('month', coalesce(NEW.last_seen_at, now()))::date;
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- Remove any legacy helper if present (kept for idempotency)
DO
$$
    BEGIN
        IF EXISTS (SELECT 1
                   FROM pg_proc p
                            JOIN pg_namespace n ON n.oid = p.pronamespace
                   WHERE n.nspname = current_schema()
                     AND p.proname = 'create_monthly_partitions'
                     AND pg_get_function_identity_arguments(p.oid) = 'integer, integer') THEN
            EXECUTE format('DROP FUNCTION %I.create_monthly_partitions(int, int)', current_schema());
        END IF;
    END
$$;

-- === 4. TABLES & PRIMARY STRUCTURES ===

CREATE TABLE IF NOT EXISTS source_domains
(
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    domain_name text NOT NULL UNIQUE,
    agent_type text NOT NULL,
    max_concurrent_requests integer DEFAULT 1 NOT NULL,
    api_endpoint text,
    notes text
);

create table sources
(
    id                   bigint generated always as identity primary key,
    source_name          text not null unique,
    domain_id            bigint,
    consecutive_failures integer,
    last_success_date    timestamp with time zone,
    last_failure_date    timestamp with time zone,
    target               text not null,
    last_checked_date    timestamp with time zone,
    strategy             text,
    keywords             text,
    is_active            boolean default true not null,
    purpose              text default 'lead_generation'::text not null,
    next_release_date    timestamp with time zone,
    last_known_item_id   text,
    constraint fk_sources_domain foreign key (domain_id) references source_domains (id) on delete set null
);

CREATE TABLE IF NOT EXISTS acquisition_router
(
    lead_uuid       uuid PRIMARY KEY,
    partition_month date        NOT NULL, -- set by trigger
    source_id       bigint,
    item_url        text,
    first_seen_at   timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT fk_router_source FOREIGN KEY (source_id) REFERENCES sources (id) ON DELETE SET NULL
);

-- Native partitioned parents with composite PK including partition key
CREATE TABLE IF NOT EXISTS acquisition_log
(
    id        bigserial,
    lead_uuid uuid        NOT NULL,
    source_id bigint,
    seen_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (id, seen_at),
    CONSTRAINT fk_acq_source FOREIGN KEY (source_id) REFERENCES sources (id) ON DELETE SET NULL
) PARTITION BY RANGE (seen_at);

CREATE TABLE IF NOT EXISTS cases
(
    id               bigserial,
    lead_uuid        uuid,
    public_uuid      uuid                 DEFAULT gen_random_uuid(),
    title            text        NOT NULL,
    url              text        NOT NULL,
    source_name      text,
    publication_date timestamptz NOT NULL,
    modified_date    timestamptz NOT NULL DEFAULT now(),
    triage_date      timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status           case_status NOT NULL DEFAULT 'NEW',
    -- Added to support views and spatial search
    category         text,
    severity_score   numeric(10, 2),
    location_geom    geometry(Point, 4326),
    PRIMARY KEY (id, publication_date),
    CONSTRAINT fk_cases_lead_uuid FOREIGN KEY (lead_uuid) REFERENCES acquisition_router (lead_uuid) ON DELETE SET NULL,
    CONSTRAINT cases_url_publication_date_key UNIQUE (url, publication_date)
) PARTITION BY RANGE (publication_date);
COMMENT ON TABLE cases IS 'Holds the metadata for a case, including its status and publication date.';
COMMENT ON COLUMN cases.title IS 'The title of the case.';
COMMENT ON COLUMN cases.url IS 'The URL of the case.';
COMMENT ON COLUMN cases.publication_date IS 'The publication date of the case.';
COMMENT ON COLUMN cases.modified_date IS 'The date the case was last modified.';
COMMENT ON COLUMN cases.triage_date IS 'The date the case was triaged.';
COMMENT ON COLUMN cases.status IS 'The status of the case.';
COMMENT ON COLUMN cases.category IS 'The category of the case.';
COMMENT ON COLUMN cases.severity_score IS 'The severity score of the case from 0.0 to 1.0.';
COMMENT ON COLUMN cases.location_geom IS 'The location of the case, as a geometry.';

CREATE TABLE IF NOT EXISTS case_content
(
    case_id          bigint,
    lead_uuid        uuid,
    publication_date timestamptz NOT NULL,
    full_text        text,
    full_html        text,
    search_vector    tsvector,
    PRIMARY KEY (case_id, publication_date),
    CONSTRAINT fk_case_content_case FOREIGN KEY (case_id, publication_date) REFERENCES cases (id, publication_date) ON DELETE CASCADE
) PARTITION BY RANGE (publication_date);
COMMENT ON TABLE case_content IS 'Holds the full text of a case, including full HTML.';
COMMENT ON COLUMN case_content.full_text IS 'The full text of the case, without HTML.';
COMMENT ON COLUMN case_content.full_html IS 'The full text of the case, with HTML.';
COMMENT ON COLUMN case_content.lead_uuid IS 'The UUID of the lead that owns this case.';

-- Investigations live in this schema and use the enum for consistency
CREATE TABLE IF NOT EXISTS investigations
(
    id                bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_uuid       uuid                 NOT NULL UNIQUE DEFAULT gen_random_uuid(),
    name              text                 NOT NULL,
    status            investigation_status NOT NULL        DEFAULT 'ACTIVE',
    summary           text,
    version           integer              NOT NULL        DEFAULT 1,
    parent_version_id integer,
    created_date      timestamptz                          DEFAULT CURRENT_TIMESTAMP,
    modified_date     timestamptz                          DEFAULT now(),
    CONSTRAINT valid_version_check CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS investigation_nodes
(
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    investigation_id bigint    NOT NULL,
    node_type        node_type NOT NULL,
    node_id          bigint,
    pos_x            integer DEFAULT 0,
    pos_y            integer DEFAULT 0,
    note_text        text,
    CONSTRAINT fk_node_investigation FOREIGN KEY (investigation_id) REFERENCES investigations (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS investigation_links
(
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    investigation_id bigint NOT NULL,
    node_a_id        bigint NOT NULL,
    node_b_id        bigint NOT NULL,
    node_min_id      bigint GENERATED ALWAYS AS (LEAST(node_a_id, node_b_id)) STORED,
    node_max_id      bigint GENERATED ALWAYS AS (GREATEST(node_a_id, node_b_id)) STORED,
    CONSTRAINT fk_link_investigation FOREIGN KEY (investigation_id) REFERENCES investigations (id) ON DELETE CASCADE,
    CONSTRAINT fk_link_node_a FOREIGN KEY (node_a_id) REFERENCES investigation_nodes (id) ON DELETE CASCADE,
    CONSTRAINT fk_link_node_b FOREIGN KEY (node_b_id) REFERENCES investigation_nodes (id) ON DELETE CASCADE,
    CONSTRAINT chk_no_self_link CHECK (node_a_id <> node_b_id),
    CONSTRAINT ux_investigation_edge_unique UNIQUE (investigation_id, node_min_id, node_max_id)
);

CREATE TABLE IF NOT EXISTS schema_version
(
    version integer NOT NULL
);

-- === 5. TRIGGERS ===

DROP TRIGGER IF EXISTS trg_cases_touch ON cases;
CREATE TRIGGER trg_cases_touch
    BEFORE UPDATE
    ON cases
    FOR EACH ROW
EXECUTE FUNCTION touch_modified();

DROP TRIGGER IF EXISTS trg_investigations_touch ON investigations;
CREATE TRIGGER trg_investigations_touch
    BEFORE UPDATE
    ON investigations
    FOR EACH ROW
EXECUTE FUNCTION touch_modified();

DROP TRIGGER IF EXISTS trg_case_content_tsv ON case_content;
CREATE TRIGGER trg_case_content_tsv
    BEFORE INSERT OR UPDATE
    ON case_content
    FOR EACH ROW
EXECUTE FUNCTION cases_tsvector_update();

DROP TRIGGER IF EXISTS trg_router_partition_month ON acquisition_router;
CREATE TRIGGER trg_router_partition_month
    BEFORE INSERT OR UPDATE
    ON acquisition_router
    FOR EACH ROW
EXECUTE FUNCTION update_router_partition_month();

-- === 6. INDEXES ===
-- Parent-level, non-unique performance indexes (partitioned indexes)
CREATE INDEX IF NOT EXISTS idx_acq_lead_uuid ON acquisition_log (lead_uuid);
CREATE INDEX IF NOT EXISTS idx_cases_status_pubdate_desc ON cases (status, publication_date DESC);
CREATE INDEX IF NOT EXISTS idx_case_content_tsv ON case_content USING GIN (search_vector);
-- Spatial index for geo queries on cases
CREATE INDEX IF NOT EXISTS idx_cases_location_geom ON cases USING GIST (location_geom);

-- === 7. pg_partman INTEGRATION ===

-- 7.0 Clean any stale partman configuration for these parents (important if schema was dropped earlier)
/*
DO
$$
    BEGIN
        DELETE
        FROM partman.part_config_sub
        WHERE sub_parent IN (
                             format('%I.%I', current_schema(), 'acquisition_log'),
                             format('%I.%I', current_schema(), 'cases'),
                             format('%I.%I', current_schema(), 'case_content')
            );

        DELETE
        FROM partman.part_config
        WHERE parent_table IN (
                               format('%I.%I', current_schema(), 'acquisition_log'),
                               format('%I.%I', current_schema(), 'cases'),
                               format('%I.%I', current_schema(), 'case_content')
            );
    END
$$;
*/
-- 7.1 Template tables define per-partition indexes/constraints

DROP TABLE IF EXISTS acquisition_log_template CASCADE;
CREATE TABLE acquisition_log_template
(
    LIKE acquisition_log INCLUDING ALL
);

-- BRIN for time-series scans inside each child
CREATE INDEX acquisition_log_template_brin_seen
    ON acquisition_log_template
        USING BRIN (seen_at) WITH (pages_per_range = 64);

DROP TABLE IF EXISTS cases_template CASCADE;
CREATE TABLE cases_template
(
    LIKE cases INCLUDING ALL
);

-- Per-partition uniqueness (legal on children)
CREATE UNIQUE INDEX cases_template_ux_url ON cases_template (url);
CREATE UNIQUE INDEX cases_template_ux_public_uuid ON cases_template (public_uuid);
CREATE UNIQUE INDEX cases_template_ux_lead_uuid ON cases_template (lead_uuid) WHERE lead_uuid IS NOT NULL;

-- Optional: partial index to speed dominant filter
CREATE INDEX cases_template_active_pub_desc
    ON cases_template (publication_date DESC)
    WHERE status = 'ACTIVE';

DROP TABLE IF EXISTS case_content_template CASCADE;
CREATE TABLE case_content_template
(
    LIKE case_content INCLUDING ALL
);

CREATE INDEX case_content_template_tsv
    ON case_content_template USING GIN (search_vector);
CREATE INDEX case_content_template_case_id
    ON case_content_template (case_id);

-- 7.2 Register parents with pg_partman (fresh)
SELECT partman.create_parent(
               p_parent_table := format('%I.%I', current_schema(), 'acquisition_log'),
               p_control := 'seen_at',
               p_type := 'range',
               p_interval := '1 month',
               p_premake := 2,
               p_start_partition := to_char(date_trunc('month', now()), 'YYYY-MM-DD')
       );

SELECT partman.create_parent(
               p_parent_table := format('%I.%I', current_schema(), 'cases'),
               p_control := 'publication_date',
               p_type := 'range',
               p_interval := '1 month',
               p_premake := 2,
               p_start_partition := to_char(date_trunc('month', now()), 'YYYY-MM-DD')
       );

SELECT partman.create_parent(
               p_parent_table := format('%I.%I', current_schema(), 'case_content'),
               p_control := 'publication_date',
               p_type := 'range',
               p_interval := '1 month',
               p_premake := 2,
               p_start_partition := to_char(date_trunc('month', now()), 'YYYY-MM-DD')
       );

-- 7.3 Attach templates and tune partman settings
UPDATE partman.part_config
SET template_table           = format('%I.%I', current_schema(), 'acquisition_log_template'),
    premake                  = 2,
    infinite_time_partitions = true
WHERE parent_table = format('%I.%I', current_schema(), 'acquisition_log');

UPDATE partman.part_config
SET template_table           = format('%I.%I', current_schema(), 'cases_template'),
    premake                  = 2,
    infinite_time_partitions = true
WHERE parent_table = format('%I.%I', current_schema(), 'cases');

UPDATE partman.part_config
SET template_table           = format('%I.%I', current_schema(), 'case_content_template'),
    premake                  = 2,
    infinite_time_partitions = true
WHERE parent_table = format('%I.%I', current_schema(), 'case_content');

-- 7.4 Create current & next partitions immediately
SELECT partman.run_maintenance(format('%I.%I', current_schema(), 'acquisition_log'));
SELECT partman.run_maintenance(format('%I.%I', current_schema(), 'cases'));
SELECT partman.run_maintenance(format('%I.%I', current_schema(), 'case_content'));

-- 7.5 (Optional) Schedule ongoing maintenance with pg_cron if available
CREATE EXTENSION IF NOT EXISTS pg_cron; -- requires pg_cron to be installed on the instance
SELECT cron.schedule(
               'partman-maint-acqlog',
               '*/10 * * * *',
               format($$SELECT partman.run_maintenance('%I.%I')$$, current_schema(), 'acquisition_log')
       );
SELECT cron.schedule(
               'partman-maint-cases',
               '*/10 * * * *',
               format($$SELECT partman.run_maintenance('%I.%I')$$, current_schema(), 'cases')
       );
SELECT cron.schedule(
               'partman-maint-content',
               '*/10 * * * *',
               format($$SELECT partman.run_maintenance('%I.%I')$$, current_schema(), 'case_content')
       );

-- === 9. INITIAL DATA ===
INSERT INTO schema_version (version)
VALUES (1)
ON CONFLICT DO NOTHING;

-- === 10. ADD MISSING TABLES AND VIEWS ===

-- system_tasks
CREATE TABLE IF NOT EXISTS system_tasks
(
    task_name     text NOT NULL,
    status        text NOT NULL,
    last_run_date timestamptz,
    notes         text,
    CONSTRAINT system_tasks_status_check CHECK (upper(status) = ANY (ARRAY ['PENDING','IN_PROGRESS','COMPLETE']))
);
ALTER TABLE system_tasks
    OWNER TO hunter_admin;
COMMENT ON TABLE system_tasks IS 'The application''s internal startup and maintenance checklist.';
COMMENT ON COLUMN system_tasks.task_name IS 'The unique, programmatic name of the maintenance task.';
COMMENT ON COLUMN system_tasks.status IS 'The current state of the task, used by the application to know what needs to be run.';
INSERT INTO system_tasks (task_name, status, last_run_date, notes)
VALUES ('CHECK_MODEL_STALENESS', 'PENDING', NULL, NULL),
       ('RUN_DATA_BALANCER', 'PENDING', NULL, NULL),
       ('ARCHIVE_OLD_LEADS', 'PENDING', NULL, NULL)
ON CONFLICT DO NOTHING;
ALTER TABLE ONLY system_tasks
    ADD CONSTRAINT system_tasks_pkey PRIMARY KEY (task_name);
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE system_tasks TO hunter_app_user;

-- processed_files_log
CREATE TABLE IF NOT EXISTS processed_files_log
(
    file_hash             text NOT NULL,
    original_filename     text NOT NULL,
    metadata_type         text,
    canonical_metadata    jsonb,
    processed_as_category text,
    process_date          timestamptz DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE processed_files_log
    OWNER TO hunter_admin;
COMMENT ON TABLE processed_files_log IS 'Master journal for manually acquired local files (PDFs, etc.) to prevent reprocessing.';
COMMENT ON COLUMN processed_files_log.file_hash IS 'The SHA-256 hash of the original file, acting as its unique fingerprint.';
COMMENT ON COLUMN processed_files_log.canonical_metadata IS 'A flexible JSONB field for storing extracted, structured metadata (e.g., issue number, author, ISBN).';
ALTER TABLE ONLY processed_files_log
    ADD CONSTRAINT processed_files_log_pkey PRIMARY KEY (file_hash);
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE processed_files_log TO hunter_app_user;

CREATE TABLE IF NOT EXISTS processed_file_outputs
(
    id               integer NOT NULL,
    parent_file_hash text    NOT NULL,
    output_path      text    NOT NULL
);
ALTER TABLE processed_file_outputs
    OWNER TO hunter_admin;
COMMENT ON TABLE processed_file_outputs IS 'A manifest linking a processed file to all of its generated output text chunks.';
ALTER TABLE processed_file_outputs
    ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME processed_file_outputs_id_seq
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1
        );
SELECT pg_catalog.setval('processed_file_outputs_id_seq', 1, false);
ALTER TABLE ONLY processed_file_outputs
    ADD CONSTRAINT processed_file_outputs_output_path_key UNIQUE (output_path);
ALTER TABLE ONLY processed_file_outputs
    ADD CONSTRAINT processed_file_outputs_pkey PRIMARY KEY (id);
ALTER TABLE ONLY processed_file_outputs
    ADD CONSTRAINT fk_output_to_parent_log FOREIGN KEY (parent_file_hash) REFERENCES processed_files_log (file_hash) ON DELETE CASCADE;
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE processed_file_outputs TO hunter_app_user;
GRANT SELECT, USAGE ON SEQUENCE processed_file_outputs_id_seq TO hunter_app_user;

-- model_metadata
CREATE TABLE IF NOT EXISTS model_metadata
(
    model_name          text        NOT NULL,
    train_date          timestamptz NOT NULL,
    case_word_count     integer     NOT NULL,
    not_case_word_count integer     NOT NULL,
    categories          text        NOT NULL
);
ALTER TABLE model_metadata
    OWNER TO hunter_admin;
COMMENT ON TABLE model_metadata IS 'The "birth certificate" for our trained AI models, used to track staleness.';
COMMENT ON COLUMN model_metadata.case_word_count IS 'The total word count of the ''case'' data the model was trained on, used for staleness checks.';
COMMENT ON COLUMN model_metadata.not_case_word_count IS 'The total word count of the ''not_a_case'' data the model was trained on, used for staleness checks.';
ALTER TABLE ONLY model_metadata
    ADD CONSTRAINT model_metadata_pkey PRIMARY KEY (model_name);
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE model_metadata TO hunter_app_user;

-- media_evidence with composite FK to cases
CREATE TABLE IF NOT EXISTS media_evidence
(
    id                    integer     NOT NULL,
    public_uuid           uuid        NOT NULL,
    case_id               bigint      NOT NULL,
    case_publication_date timestamptz NOT NULL,
    location              text        NOT NULL,
    location_type         text        NOT NULL,
    thumbnail_path        text,
    description           text,
    evidence_type         text,
    location_geom         geometry(Point, 4326),
    CONSTRAINT media_evidence_location_type_check
        CHECK (upper(location_type) = ANY (ARRAY ['LOCAL','REMOTE','ARCHIVED'])),
    CONSTRAINT media_evidence_pkey PRIMARY KEY (id),
    CONSTRAINT media_evidence_public_uuid_key UNIQUE (public_uuid),
    CONSTRAINT media_evidence_location_key UNIQUE (location),
    CONSTRAINT fk_media_evidence_case
        FOREIGN KEY (case_id, case_publication_date)
            REFERENCES cases (id, publication_date)
            ON DELETE CASCADE
);
ALTER TABLE media_evidence
    OWNER TO hunter_admin;
COMMENT ON TABLE media_evidence IS 'The evidence locker for all non-textual intel (images, audio, maps).';
COMMENT ON COLUMN media_evidence.location_type IS 'Enum-style field indicating if the evidence location is LOCAL, REMOTE, or ARCHIVED.';
COMMENT ON COLUMN media_evidence.thumbnail_path IS 'A local file path to a small, pre-generated thumbnail for fast GUI previews.';
COMMENT ON COLUMN media_evidence.location_geom IS 'The precise geographic coordinate where a piece of evidence was captured, for fine-grained spatial analysis.';
ALTER TABLE media_evidence
    ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
        SEQUENCE NAME media_evidence_id_seq
        START WITH 1
        INCREMENT BY 1
        NO MINVALUE
        NO MAXVALUE
        CACHE 1
        );
SELECT pg_catalog.setval('media_evidence_id_seq', 1, false);
CREATE INDEX IF NOT EXISTS idx_media_evidence_case_ref
    ON media_evidence (case_id, case_publication_date);
CREATE INDEX IF NOT EXISTS idx_media_evidence_evidence_type
    ON media_evidence (evidence_type);
CREATE INDEX IF NOT EXISTS idx_media_evidence_location_geom
    ON media_evidence USING gist (location_geom);
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE media_evidence TO hunter_app_user;
GRANT SELECT, USAGE ON SEQUENCE media_evidence_id_seq TO hunter_app_user;

-- Views adjusted for enum types and available columns
CREATE OR REPLACE VIEW case_summaries AS
SELECT c.id,
       c.public_uuid,
       c.title,
       c.status,
       c.category,
       c.severity_score,
       c.publication_date,
       c.modified_date,
       EXISTS (SELECT 1 FROM media_evidence me WHERE me.case_id = c.id)                             AS has_media,
       EXISTS (SELECT 1 FROM investigation_nodes n WHERE n.node_type = 'CASE' AND n.node_id = c.id) AS in_investigation
FROM cases c;
ALTER VIEW case_summaries OWNER TO hunter_admin;
COMMENT ON VIEW case_summaries IS 'A clean summary view of cases, indicating if they have media or are part of an investigation.';

CREATE OR REPLACE VIEW investigation_complexity AS
SELECT i.id,
       i.name,
       i.status,
       count(DISTINCT n.id)                                                                       AS total_nodes,
       count(DISTINCT l.id)                                                                       AS total_links,
       count(DISTINCT CASE WHEN n.node_type = 'CASE' THEN n.id END)                               AS case_count,
       count(DISTINCT CASE WHEN n.node_type = 'MEDIA' THEN n.id END)                              AS media_count,
       count(DISTINCT CASE WHEN n.node_type = 'NOTE' THEN n.id END)                               AS note_count,
       (count(DISTINCT l.id)::double precision / NULLIF(count(DISTINCT n.id), 0))::numeric(10, 2) AS connectivity_ratio
FROM investigations i
         LEFT JOIN investigation_nodes n ON i.id = n.investigation_id
         LEFT JOIN investigation_links l ON i.id = l.investigation_id
GROUP BY i.id, i.name, i.status;
ALTER VIEW investigation_complexity OWNER TO hunter_admin;
COMMENT ON VIEW investigation_complexity IS 'Provides metrics about the complexity of each investigation.';

CREATE OR REPLACE VIEW case_category_stats AS
SELECT c.category,
       count(*)                                    AS total_cases,
       count(*) FILTER (WHERE c.status = 'NEW')    AS new_cases,
       count(*) FILTER (WHERE c.status = 'ACTIVE') AS active_cases,
       avg(c.severity_score)::numeric(10, 2)       AS avg_severity
FROM cases c
WHERE c.category IS NOT NULL
GROUP BY c.category;
ALTER VIEW case_category_stats OWNER TO hunter_admin;
COMMENT ON VIEW case_category_stats IS 'A pivoted summary view of case statistics, grouped by category.';

-- Active investigations view (final definition)
CREATE OR REPLACE VIEW active_investigations AS
SELECT i.id,
       i.public_uuid,
       i.name,
       i.status,
       i.summary,
       i.version,
       i.parent_version_id,
       i.created_date,
       i.modified_date,
       count(DISTINCT n.id) AS total_nodes,
       count(DISTINCT l.id) AS total_links,
       max(i.modified_date) AS last_activity
FROM investigations i
         LEFT JOIN investigation_nodes n ON i.id = n.investigation_id
         LEFT JOIN investigation_links l ON i.id = l.investigation_id
WHERE i.status = 'ACTIVE'
GROUP BY i.id;
ALTER VIEW active_investigations OWNER TO hunter_admin;
COMMENT ON VIEW active_investigations IS 'Shows all active investigations with their node and link counts.';

-- missing functions
--
-- Name: generate_case_summary(integer); Type: FUNCTION; Schema: public; Owner: hunter_admin
--

CREATE FUNCTION generate_case_summary(p_case_id bigint) RETURNS json
    LANGUAGE plpgsql
AS
$$
DECLARE
    result json;
BEGIN
    SELECT json_build_object(
                   'case_info',
                   json_build_object('id', c.id, 'title', c.title, 'status', c.status, 'category', c.category,
                                     'severity', c.severity_score, 'publication_date', c.publication_date, 'location',
                                     CASE
                                         WHEN c.location_geom IS NOT NULL THEN json_build_object('lat',
                                                                                                 ST_Y(c.location_geom),
                                                                                                 'lon',
                                                                                                 ST_X(c.location_geom)) END),
                   'content_summary',
                   json_build_object('text_length', length(cc.full_text), 'has_html', cc.full_html IS NOT NULL),
                   'media_evidence',
                   (SELECT json_agg(json_build_object('id', me.id, 'type', me.evidence_type, 'description',
                                                      me.description))
                    FROM media_evidence me
                    WHERE me.case_id = p_case_id),
                   'investigations', (SELECT json_agg(json_build_object('id', i.id, 'name', i.name, 'status', i.status))
                                      FROM investigations i
                                               JOIN investigation_nodes in1 ON i.id = in1.investigation_id
                                      WHERE in1.node_id = p_case_id
                                        AND in1.node_type = 'CASE')
           )
    INTO result
    FROM cases c
             LEFT JOIN case_content cc ON c.id = cc.case_id
    WHERE c.id = p_case_id;
    RETURN result;
END;
$$;


ALTER FUNCTION generate_case_summary(p_case_id bigint) OWNER TO hunter_admin;

--
-- Name: FUNCTION generate_case_summary(p_case_id integer); Type: COMMENT; Schema: public; Owner: hunter_admin
--

COMMENT ON FUNCTION generate_case_summary(p_case_id bigint) IS 'Generates a complete, aggregated JSON summary for a single case, including its content, media, and investigation links.';


--
-- Name: get_case_complexity(integer); Type: FUNCTION; Schema: public; Owner: hunter_admin
--

CREATE FUNCTION get_case_complexity(p_case_id bigint)
    RETURNS TABLE
            (
                case_title               text,
                media_count              bigint,
                investigation_references bigint,
                linked_cases             bigint,
                complexity_score         numeric
            )
    LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN QUERY
        WITH case_data AS (SELECT c.title,
                                  COUNT(DISTINCT me.id)                as media_count,
                                  COUNT(DISTINCT in1.investigation_id) as investigation_refs,
                                  COUNT(DISTINCT il.node_b_id)         as linked_cases
                           FROM cases c
                                    LEFT JOIN media_evidence me ON c.id = me.case_id
                                    LEFT JOIN investigation_nodes in1 ON c.id = in1.node_id
                               AND in1.node_type = 'CASE'
                                    LEFT JOIN investigation_links il ON in1.id = il.node_a_id
                           WHERE c.id = p_case_id
                           GROUP BY c.title)
        SELECT cd.title,
               cd.media_count,
               cd.investigation_refs,
               cd.linked_cases,
               (cd.media_count * 0.3 + cd.investigation_refs * 0.4 + cd.linked_cases * 0.3)::numeric
                   as complexity_score
        FROM case_data cd;
END;
$$;


ALTER FUNCTION get_case_complexity(p_case_id bigint) OWNER TO hunter_admin;

--
-- Name: FUNCTION get_case_complexity(p_case_id integer); Type: COMMENT; Schema: public; Owner: hunter_admin
--

COMMENT ON FUNCTION get_case_complexity(p_case_id bigint) IS 'Calculates a complexity score for a case based on its relationships and evidence.';


--
-- Name: get_case_statistics(); Type: FUNCTION; Schema: public; Owner: hunter_admin
--

CREATE OR REPLACE FUNCTION get_case_statistics()
    RETURNS TABLE
            (
                total_cases         bigint,
                cases_with_location bigint,
                cases_by_status     json,
                avg_severity        numeric,
                cases_last_24h      bigint
            )
    LANGUAGE plpgsql
AS
$$
BEGIN
    RETURN QUERY
        SELECT COUNT(*)::BIGINT,
               COUNT(location_geom)::BIGINT,
               -- This subquery is now self-contained and unambiguous
               (SELECT json_object_agg(status, cnt)
                FROM (SELECT status, COUNT(*) AS cnt FROM cases GROUP BY status) AS status_counts)::JSON,
               AVG(severity_score)::NUMERIC,
               COUNT(CASE WHEN triage_date >= NOW() - INTERVAL '24 hours' THEN 1 END)::BIGINT
        FROM cases;
END;
$$;

ALTER FUNCTION get_case_statistics() OWNER TO hunter_admin;

--
-- Name: FUNCTION get_case_statistics(); Type: COMMENT; Schema: public; Owner: hunter_admin
--

COMMENT ON FUNCTION get_case_statistics() IS 'Generates comprehensive statistics about cases in the system.';

--
-- Name: perform_custom_maintenance(); Type: FUNCTION; Schema: public; Owner: hunter_admin
--

CREATE FUNCTION perform_custom_maintenance()
    RETURNS TABLE
            (
                maintenance_task text,
                result           text
            )
    LANGUAGE plpgsql
AS
$$
DECLARE
    old_date timestamp with time zone := current_timestamp - interval '90 days';
BEGIN
    -- 1. Archive old investigations
    UPDATE investigations
    SET status = 'ARCHIVED'
    WHERE status = 'COLD_CASE'
      AND modified_date < old_date
      AND NOT EXISTS (SELECT 1
                      FROM investigation_nodes n
                      WHERE n.investigation_id = investigations.id
                        AND n.node_type = 'CASE');

    maintenance_task := 'Archive old investigations';
    result := format('%s investigations archived', FOUND);
    RETURN NEXT;

    -- 2. Clean up orphaned media evidence thumbnails
    WITH orphaned_media AS (SELECT me.id, me.thumbnail_path
                            FROM media_evidence me
                                     LEFT JOIN cases c ON me.case_id = c.id
                            WHERE c.id IS NULL
                              AND me.thumbnail_path IS NOT NULL)
    UPDATE media_evidence me
    SET thumbnail_path = NULL
    FROM orphaned_media om
    WHERE me.id = om.id;

    maintenance_task := 'Clean orphaned thumbnails';
    result := format('%s thumbnails cleaned', FOUND);
    RETURN NEXT;

    -- 3. Update source health metrics
    UPDATE sources s
    SET consecutive_failures = 0
    WHERE consecutive_failures > 0
      AND last_success_date > last_failure_date;

    maintenance_task := 'Update source health';
    result := format('%s sources health metrics updated', FOUND);
    RETURN NEXT;

    -- 4. Identify potential duplicate cases
    WITH potential_duplicates AS (SELECT c1.id    as id1,
                                         c2.id    as id2,
                                         c1.title as title1,
                                         c2.title as title2
                                  FROM cases c1
                                           JOIN cases c2 ON
                                      c1.id < c2.id AND
                                      similarity(c1.title, c2.title) > 0.9 AND
                                      abs(extract(epoch from (c1.publication_date - c2.publication_date))) < 86400
                                  LIMIT 100)
    SELECT format('%s potential duplicates found', count(*))
    INTO result
    FROM potential_duplicates;

    maintenance_task := 'Duplicate case detection';
    RETURN NEXT;

    -- 5. Update search vector for cases with NULL vectors
    UPDATE case_content cc
    SET search_vector =
            setweight(to_tsvector('english', coalesce(c.title, '')), 'A') ||
            setweight(to_tsvector('english', coalesce(cc.full_text, '')), 'B')
    FROM cases c
    WHERE cc.case_id = c.id
      AND cc.search_vector IS NULL;

    maintenance_task := 'Update missing search vectors';
    result := format('%s search vectors updated', FOUND);
    RETURN NEXT;
END;
$$;


ALTER FUNCTION perform_custom_maintenance() OWNER TO hunter_admin;

--
-- Name: FUNCTION perform_custom_maintenance(); Type: COMMENT; Schema: public; Owner: hunter_admin
--

COMMENT ON FUNCTION perform_custom_maintenance() IS 'Performs various maintenance tasks to keep the database healthy and efficient.';

-- === DYNAMIC PERMISSIONS & OWNERSHIP ===
-- === MUST BE RUN AFTER ALL TABLES HAVE BEEN CREATED ===
DO
$$
    DECLARE
        obj_name         text;
        func_signature   text;
        -- Tables that the app_user can only read from
        read_only_tables text[] := ARRAY [
            'sources',
            'source_domains',
            'model_metadata',
            'schema_version'
            ];
        -- Tables that the app_user should have NO access to
        excluded_tables  text[] := ARRAY [
            'acquisition_log_template',
            'cases_template',
            'case_content_template'
            ];
    BEGIN
        -- Grant Table Permissions
        FOR obj_name IN
            SELECT tablename FROM pg_tables WHERE schemaname = current_schema()
            LOOP
                -- First, always set ownership for the admin role
                EXECUTE format('ALTER TABLE %I OWNER TO %I', obj_name, 'hunter_admin');

                -- Then, grant permissions to the app user, but ONLY if the table is not excluded
                IF NOT (obj_name = ANY (excluded_tables)) THEN
                    IF obj_name = ANY (read_only_tables) THEN
                        -- Grant read-only access for config/lookup tables
                        EXECUTE format('GRANT SELECT ON TABLE %I TO %I', obj_name, 'hunter_app_user');
                        IF obj_name = 'sources' THEN
                            EXECUTE format('GRANT UPDATE (
                                          consecutive_failures,
                                          last_success_date,
                                          last_failure_date,
                                          last_checked_date,
                                          next_release_date,
                                          last_known_item_id
                                ) ON %I TO %I', obj_name, 'hunter_app_user');

                        end if;
                    ELSE
                        -- Grant full access for all other (non-excluded) transactional tables
                        EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE %I TO %I', obj_name,
                                       'hunter_app_user');
                    END IF;
                END IF; -- End of exclusion check
            END LOOP;

        -- Grant View Permissions (always read-only)
        FOR obj_name IN
            SELECT table_name FROM information_schema.views WHERE table_schema = current_schema()
            LOOP
                EXECUTE format('ALTER VIEW %I OWNER TO %I', obj_name, 'hunter_admin');
                EXECUTE format('GRANT SELECT ON TABLE %I TO %I', obj_name, 'hunter_app_user');
            END LOOP;

        -- Grant Sequence Permissions
        FOR obj_name IN
            SELECT sequence_name FROM information_schema.sequences WHERE sequence_schema = current_schema()
            LOOP
                EXECUTE format('ALTER SEQUENCE %I OWNER TO %I', obj_name, 'hunter_admin');
                EXECUTE format('GRANT USAGE, SELECT ON SEQUENCE %I TO %I', obj_name, 'hunter_app_user');
            END LOOP;

        -- Grant Function Permissions
        FOR func_signature IN
            SELECT p.proname || '(' || pg_get_function_identity_arguments(p.oid) || ')'
            FROM pg_proc p
                     JOIN pg_namespace n ON p.pronamespace = n.oid
                     LEFT JOIN pg_depend d ON d.objid = p.oid AND d.deptype = 'e'
            WHERE n.nspname = current_schema()
              AND d.refobjid IS NULL
            LOOP
                EXECUTE format('ALTER FUNCTION %s OWNER TO %I', func_signature, 'hunter_admin');
                EXECUTE format('GRANT EXECUTE ON FUNCTION %s TO %I', func_signature, 'hunter_app_user');
            END LOOP;

        GRANT USAGE ON SCHEMA almanac TO hunter_app_user;
    END;
$$;
-- Reset search path to default for the session
SET search_path = "$user", public;