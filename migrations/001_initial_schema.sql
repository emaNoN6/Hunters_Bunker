/*
 * # ==========================================================
 * # Hunter's Command Console - Initial schema creation
 * # File: 001_initial_schema_sql
 * # Last Modified: 8/3/25
 * #
 * # ==========================================================
 */

SET SEARCH_PATH = public;

-- === 1. EXTENSIONS ===
-- Extensions are database-level, so they're already available

-- === 2. FUNCTIONS & TRIGGERS ===

CREATE OR REPLACE FUNCTION update_modified_column()
    RETURNS TRIGGER AS $$
BEGIN
    -- NEW is a special variable holding the new version of the row
    NEW.modified_date = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_nearby_cases(lat double precision, lon double precision, radius_meters double precision)
    RETURNS TABLE(id integer, title text, distance_meters double precision) AS $$
BEGIN
    RETURN QUERY
        SELECT c.id, c.title, ST_Distance(c.location_geom::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography) as distance
        FROM cases c
        WHERE ST_DWithin(c.location_geom::geography, ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography, radius_meters)
        ORDER BY distance;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cases_tsvector_update()
    RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector =
            setweight(to_tsvector('english', coalesce(NEW.title,'')), 'A') ||
            setweight(to_tsvector('english', coalesce(NEW.full_text,'')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_case_statistics()
    RETURNS TABLE(total_cases bigint, cases_with_location bigint, cases_by_status json, avg_severity numeric, cases_last_24h bigint) AS $$
BEGIN
    RETURN QUERY
        SELECT
            COUNT(*)::BIGINT as total_cases,
            COUNT(location_geom)::BIGINT as cases_with_location,
            json_object_agg(status, cnt)::JSON as cases_by_status,
            AVG(severity_score)::NUMERIC as avg_severity,
            COUNT(CASE WHEN triage_date >= NOW() - INTERVAL '24 hours' THEN 1 END)::BIGINT as cases_last_24h
        FROM cases c
                 LEFT JOIN (
            SELECT status, COUNT(*) as cnt
            FROM cases
            GROUP BY status
        ) s ON true;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION get_case_complexity(p_case_id integer)
    RETURNS TABLE(case_title text, media_count bigint, investigation_references bigint, linked_cases bigint, complexity_score numeric) AS $$
BEGIN
    RETURN QUERY
        WITH case_data AS (
            SELECT
                c.title,
                COUNT(DISTINCT me.id) as media_count,
                COUNT(DISTINCT in1.investigation_id) as investigation_refs,
                COUNT(DISTINCT il.node_b_id) as linked_cases
            FROM cases c
                     LEFT JOIN media_evidence me ON c.id = me.case_id
                     LEFT JOIN investigation_nodes in1 ON c.id = in1.node_id
                AND in1.node_type = 'CASE'
                     LEFT JOIN investigation_links il ON in1.id = il.node_a_id
            WHERE c.id = p_case_id
            GROUP BY c.title
        )
        SELECT
            cd.title,
            cd.media_count,
            cd.investigation_refs,
            cd.linked_cases,
            (cd.media_count * 0.3 + cd.investigation_refs * 0.4 + cd.linked_cases * 0.3)::numeric
                as complexity_score
        FROM case_data cd;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION perform_custom_maintenance()
    RETURNS TABLE(maintenance_task text, result text) AS $$
DECLARE
    old_date timestamp with time zone := current_timestamp - interval '90 days';
BEGIN
    -- 1. Archive old investigations
    UPDATE investigations
    SET status = 'ARCHIVED'
    WHERE status = 'COLD_CASE'
      AND modified_date < old_date
      AND NOT EXISTS (
        SELECT 1 FROM investigation_nodes n
        WHERE n.investigation_id = investigations.id
          AND n.node_type = 'CASE'
    );

    maintenance_task := 'Archive old investigations';
    result := format('%s investigations archived', FOUND);
    RETURN NEXT;

    -- 2. Clean up orphaned media evidence thumbnails
    WITH orphaned_media AS (
        SELECT me.id, me.thumbnail_path
        FROM media_evidence me
                 LEFT JOIN cases c ON me.case_id = c.id
        WHERE c.id IS NULL
          AND me.thumbnail_path IS NOT NULL
    )
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
    WITH potential_duplicates AS (
        SELECT
            c1.id as id1,
            c2.id as id2,
            c1.title as title1,
            c2.title as title2
        FROM cases c1
                 JOIN cases c2 ON
            c1.id < c2.id AND
            similarity(c1.title, c2.title) > 0.9 AND
            abs(extract(epoch from (c1.publication_date - c2.publication_date))) < 86400
        LIMIT 100
    )
    SELECT format('%s potential duplicates found', count(*))
    INTO result
    FROM potential_duplicates;

    maintenance_task := 'Duplicate case detection';
    RETURN NEXT;

    -- 5. Update search vector for cases with NULL vectors
    UPDATE case_content cc
    SET search_vector =
            setweight(to_tsvector('english', coalesce(c.title,'')), 'A') ||
            setweight(to_trvector('english', coalesce(cc.full_text,'')), 'B')
    FROM cases c
    WHERE cc.case_id = c.id
      AND cc.search_vector IS NULL;

    maintenance_task := 'Update missing search vectors';
    result := format('%s search vectors updated', FOUND);
    RETURN NEXT;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION generate_case_summary(p_case_id integer)
    RETURNS json AS $$
DECLARE result json;
BEGIN
    SELECT json_build_object(
                   'case_info', json_build_object('id', c.id, 'title', c.title, 'status', c.status, 'category', c.category, 'severity', c.severity_score, 'publication_date', c.publication_date, 'location', CASE WHEN c.location_geom IS NOT NULL THEN json_build_object('lat', ST_Y(c.location_geom), 'lon', ST_X(c.location_geom)) END),
                   'content_summary', json_build_object('text_length', length(cc.full_text), 'has_html', cc.full_html IS NOT NULL),
                   'media_evidence', (SELECT json_agg(json_build_object('id', me.id, 'type', me.evidence_type, 'description', me.description)) FROM media_evidence me WHERE me.case_id = p_case_id),
                   'investigations', (SELECT json_agg(json_build_object('id', i.id, 'name', i.name, 'status', i.status)) FROM investigations i JOIN investigation_nodes in1 ON i.id = in1.investigation_id WHERE in1.node_id = p_case_id AND in1.node_type = 'CASE')
           ) INTO result
    FROM cases c
             LEFT JOIN case_content cc ON c.id = cc.case_id
    WHERE c.id = p_case_id;
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- === 3. TABLES & PRIMARY STRUCTURES ===

DROP TABLE IF EXISTS public.source_domains CASCADE;
CREATE TABLE source_domains (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    domain_name text NOT NULL UNIQUE,
    agent_type text NOT NULL,
    max_concurrent_requests integer DEFAULT 1 NOT NULL,
    api_endpoint text,
    notes text
);

DROP TABLE IF EXISTS sources CASCADE;
CREATE TABLE sources (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source_name text NOT NULL UNIQUE,
    target text NOT NULL,
    strategy text,
    keywords text,
    is_active boolean DEFAULT true NOT NULL,
    purpose text DEFAULT 'lead_generation'::text NOT NULL,
    last_checked_date timestamp with time zone,
    next_release_date timestamp with time zone,
    last_known_item_id text,
    consecutive_failures integer DEFAULT 0 NOT NULL,
    last_failure_date timestamp with time zone,
    last_success_date timestamp with time zone,
    domain_id integer NOT NULL
);

DROP TABLE IF EXISTS acquisition_log CASCADE;
CREATE TABLE acquisition_log (
    item_url text NOT NULL PRIMARY KEY,
    source_id integer NOT NULL,
    title text,
    status text NOT NULL,
    notes text,
    process_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT acquisition_log_status_check CHECK ((UPPER(status) = ANY (ARRAY['PROCESSED'::text, 'IGNORED'::text, 'FAILED'::text])))
);

DROP TABLE IF EXISTS cases CASCADE;
CREATE TABLE cases (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    public_uuid uuid NOT NULL UNIQUE,
    title text NOT NULL,
    url text NOT NULL UNIQUE,
    source_name text,
    publication_date timestamp with time zone,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    modified_date timestamp with time zone,
    status text DEFAULT 'NEW'::text,
    category text DEFAULT 'UNCATEGORIZED'::text NOT NULL,
    severity_score real,
    location_geom public.geometry(Point, 4326),
    CONSTRAINT cases_status_check CHECK ((UPPER(status) = ANY (ARRAY['NEW'::text, 'ACTIVE'::text, 'ARCHIVED'::text, 'PENDING'::text, 'REJECTED'::text]))),
    CONSTRAINT valid_severity_score CHECK (((severity_score >= 0.0) AND (severity_score <= 1.0))),
    CONSTRAINT valid_coordinates CHECK (public.st_x(location_geom) >= -180 AND public.st_x(location_geom) <= 180 AND public.st_y(location_geom) >= -90 AND public.st_y(location_geom) <= 90)
);

DROP TABLE IF EXISTS case_content CASCADE;
CREATE TABLE case_content (
    case_id integer NOT NULL PRIMARY KEY,
    full_text text,
    full_html text,
    search_vector tsvector
);

DROP TABLE IF EXISTS media_evidence CASCADE;
CREATE TABLE media_evidence (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    public_uuid uuid NOT NULL UNIQUE,
    case_id integer NOT NULL,
    location text NOT NULL UNIQUE,
    location_type text NOT NULL,
    thumbnail_path text,
    description text,
    evidence_type text,
    location_geom public.geometry(Point, 4326),
    CONSTRAINT media_evidence_location_type_check CHECK ((UPPER(location_type) = ANY (ARRAY['LOCAL'::text, 'REMOTE'::text, 'ARCHIVED'::text])))
);

DROP TABLE IF EXISTS investigations CASCADE;
CREATE TABLE investigations (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    public_uuid uuid NOT NULL UNIQUE,
    name text NOT NULL,
    status text NOT NULL,
    summary text,
    version integer DEFAULT 1 NOT NULL,
    parent_version_id integer,
    created_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    modified_date timestamp with time zone,
    CONSTRAINT investigations_status_check CHECK ((UPPER(status) = ANY (ARRAY['ACTIVE'::text, 'ARCHIVED'::text, 'COLD_CASE'::text]))),
    CONSTRAINT valid_version_check CHECK ((version > 0))
);

DROP TABLE IF EXISTS investigation_nodes CASCADE;
CREATE TABLE investigation_nodes (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    investigation_id integer NOT NULL,
    node_type text NOT NULL,
    node_id integer,
    pos_x integer DEFAULT 0,
    pos_y integer DEFAULT 0,
    note_text text,
    CONSTRAINT investigation_nodes_node_type_check CHECK ((UPPER(node_type) = ANY (ARRAY['CASE'::text, 'MEDIA'::text, 'NOTE'::text])))
);

DROP TABLE IF EXISTS investigation_links CASCADE;
CREATE TABLE investigation_links (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    investigation_id integer NOT NULL,
    node_a_id integer NOT NULL,
    node_b_id integer NOT NULL,
    description text,
    CONSTRAINT prevent_self_links CHECK ((node_a_id <> node_b_id))
);

DROP TABLE IF EXISTS model_metadata CASCADE;
CREATE TABLE model_metadata (
    model_name text NOT NULL PRIMARY KEY,
    train_date timestamp with time zone NOT NULL,
    case_word_count integer NOT NULL,
    not_case_word_count integer NOT NULL,
    categories text NOT NULL
);

DROP TABLE IF EXISTS processed_files_log CASCADE;
CREATE TABLE processed_files_log (
    file_hash text NOT NULL PRIMARY KEY,
    original_filename text NOT NULL,
    metadata_type text,
    canonical_metadata jsonb,
    processed_as_category text,
    process_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);

DROP TABLE IF EXISTS processed_file_outputs CASCADE;
CREATE TABLE processed_file_outputs (
    id integer NOT NULL PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    parent_file_hash text NOT NULL,
    output_path text NOT NULL UNIQUE
);

DROP TABLE IF EXISTS system_tasks CASCADE;
CREATE TABLE system_tasks (
    task_name text NOT NULL PRIMARY KEY,
    status text NOT NULL,
    last_run_date timestamp with time zone,
    notes text,
    CONSTRAINT system_tasks_status_check CHECK ((UPPER(status) = ANY (ARRAY['PENDING'::text, 'IN_PROGRESS'::text, 'COMPLETE'::text])))
);

DROP TABLE IF EXISTS schema_version CASCADE;
CREATE TABLE schema_version (
    version integer NOT NULL
);

-- === 4. FOREIGN KEYS ===
ALTER TABLE sources ADD CONSTRAINT fk_sources_to_domain FOREIGN KEY (domain_id) REFERENCES source_domains(id) ON DELETE RESTRICT;
ALTER TABLE acquisition_log ADD CONSTRAINT fk_acquisition_log_source FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE RESTRICT;
ALTER TABLE case_content ADD CONSTRAINT fk_content_to_case FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;
ALTER TABLE media_evidence ADD CONSTRAINT fk_media_evidence_case FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE;
ALTER TABLE investigation_nodes ADD CONSTRAINT fk_investigation_nodes_investigation FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE;
ALTER TABLE investigation_links ADD CONSTRAINT fk_investigation_links_investigation FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE;
ALTER TABLE investigation_links ADD CONSTRAINT fk_investigation_links_node_a FOREIGN KEY (node_a_id) REFERENCES investigation_nodes(id) ON DELETE CASCADE;
ALTER TABLE investigation_links ADD CONSTRAINT fk_investigation_links_node_b FOREIGN KEY (node_b_id) REFERENCES investigation_nodes(id) ON DELETE CASCADE;
ALTER TABLE processed_file_outputs ADD CONSTRAINT fk_output_to_parent_log FOREIGN KEY (parent_file_hash) REFERENCES processed_files_log(file_hash) ON DELETE CASCADE;

-- === 5. TRIGGERS ===
DROP TRIGGER IF EXISTS update_cases_modtime ON cases;
DROP TRIGGER IF EXISTS update_investigations_modtime ON investigations;
DROP TRIGGER IF EXISTS update_case_search_vector ON case_content;
CREATE TRIGGER update_cases_modtime BEFORE UPDATE ON cases FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
CREATE TRIGGER update_investigations_modtime BEFORE UPDATE ON investigations FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
CREATE TRIGGER update_case_search_vector BEFORE INSERT OR UPDATE ON case_content FOR EACH ROW EXECUTE FUNCTION cases_tsvector_update();

-- === 6. INDEXES ===
CREATE INDEX IF NOT EXISTS idx_cases_status ON cases(status);
CREATE INDEX IF NOT EXISTS idx_cases_publication_date ON cases(publication_date);
CREATE INDEX IF NOT EXISTS idx_case_content_search_vector ON case_content USING gin(search_vector);
CREATE INDEX IF NOT EXISTS idx_cases_location_geom ON cases USING gist(location_geom);
CREATE INDEX IF NOT EXISTS idx_media_evidence_location_geom ON media_evidence USING gist(location_geom);
CREATE INDEX IF NOT EXISTS idx_cases_title_trgm ON cases USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_cases_status_date ON cases (status, publication_date);
CREATE INDEX IF NOT EXISTS idx_acquisition_log_process_date ON acquisition_log(process_date);
CREATE INDEX IF NOT EXISTS idx_acquisition_log_status ON acquisition_log(status);
CREATE INDEX IF NOT EXISTS idx_cases_public_uuid ON cases(public_uuid);
CREATE INDEX IF NOT EXISTS idx_cases_title_lower ON cases(lower(title));
CREATE INDEX IF NOT EXISTS idx_investigation_nodes_composite ON investigation_nodes(investigation_id, node_type);
CREATE INDEX IF NOT EXISTS idx_media_evidence_case_id ON media_evidence(case_id);
CREATE INDEX IF NOT EXISTS idx_media_evidence_evidence_type ON media_evidence(evidence_type);

-- === 7. VIEWS ===
CREATE OR REPLACE VIEW case_summaries AS
SELECT c.id, c.public_uuid, c.title, c.status, c.category, c.severity_score, c.publication_date, c.modified_date,
       (EXISTS ( SELECT 1 FROM media_evidence me WHERE (me.case_id = c.id))) AS has_media,
       (EXISTS ( SELECT 1 FROM investigation_nodes n WHERE ((n.node_type = 'CASE'::text) AND (n.node_id = c.id)))) AS in_investigation
FROM cases c;

CREATE OR REPLACE VIEW case_category_stats AS
SELECT c.category,
       count(*) AS total_cases,
       count(*) FILTER (WHERE (c.status = 'NEW'::text)) AS new_cases,
       count(*) FILTER (WHERE (c.status = 'ACTIVE'::text)) AS active_cases,
       (avg(c.severity_score))::numeric(10,2) AS avg_severity
FROM cases c
WHERE (c.category IS NOT NULL)
GROUP BY c.category;

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

CREATE OR REPLACE VIEW investigation_complexity AS
SELECT i.id,
       i.name,
       i.status,
       count(DISTINCT n.id) AS total_nodes,
       count(DISTINCT l.id) AS total_links,
       count(DISTINCT CASE WHEN n.node_type = 'CASE' THEN n.id END) AS case_count,
       count(DISTINCT CASE WHEN n.node_type = 'MEDIA' THEN n.id END) AS media_count,
       count(DISTINCT CASE WHEN n.node_type = 'NOTE' THEN n.id END) AS note_count,
       (count(DISTINCT l.id)::float / NULLIF(count(DISTINCT n.id), 0))::numeric(10,2) AS connectivity_ratio
FROM investigations i
         LEFT JOIN investigation_nodes n ON i.id = n.investigation_id
         LEFT JOIN investigation_links l ON i.id = l.investigation_id
GROUP BY i.id, i.name, i.status;

-- === 8. PERMISSIONS ===
-- Set default privileges for any new tables the admin creates
ALTER DEFAULT PRIVILEGES FOR ROLE hunter_admin IN SCHEMA public GRANT SELECT,USAGE ON SEQUENCES TO hunter_app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE hunter_admin IN SCHEMA public GRANT SELECT,INSERT,DELETE,UPDATE ON TABLES TO hunter_app_user;

-- Set ownership of tables, functions, and views
ALTER FUNCTION public.update_modified_column() OWNER TO hunter_admin;
ALTER TABLE public.source_domains OWNER TO hunter_admin;
ALTER TABLE public.sources OWNER TO hunter_admin;
ALTER TABLE public.acquisition_log OWNER TO hunter_admin;
ALTER TABLE public.cases OWNER TO hunter_admin;
ALTER TABLE public.case_content OWNER TO hunter_admin;
ALTER TABLE public.media_evidence OWNER TO hunter_admin;
ALTER TABLE public.investigations OWNER TO hunter_admin;
ALTER TABLE public.investigation_nodes OWNER TO hunter_admin;
ALTER TABLE public.investigation_links OWNER TO hunter_admin;
ALTER TABLE public.model_metadata OWNER TO hunter_admin;
ALTER TABLE public.processed_files_log OWNER TO hunter_admin;
ALTER TABLE public.processed_file_outputs OWNER TO hunter_admin;
ALTER TABLE public.system_tasks OWNER TO hunter_admin;
ALTER TABLE public.schema_version OWNER TO hunter_admin;


-- Grant permissions on existing tables
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE
    public.acquisition_log,
    public.cases,
    public.case_content, 
    public.investigation_nodes, 
    public.media_evidence, 
    public.investigation_links, 
    public.investigations,
    public.processed_file_outputs, 
    public.processed_files_log, 
    public.sources, 
    public.system_tasks TO hunter_app_user;

-- Grant READ-ONLY access to sensitive/config tables
GRANT SELECT ON TABLE 
    public.model_metadata, 
    public.schema_version, 
    public.source_domains TO hunter_app_user;

-- Grant permissions on existing sequences
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO hunter_app_user;

-- Grant SELECT on all views
GRANT SELECT ON ALL TABLES IN SCHEMA public TO hunter_app_user;

-- Grant read-only access to all our analytical views
GRANT SELECT ON public.case_summaries TO hunter_app_user;
GRANT SELECT ON public.case_category_stats TO hunter_app_user;
GRANT SELECT ON public.active_investigations TO hunter_app_user;
GRANT SELECT ON public.investigation_complexity TO hunter_app_user;

-- Grant permission to run (execute) our custom functions
GRANT EXECUTE ON FUNCTION public.get_nearby_cases TO hunter_app_user;
GRANT EXECUTE ON FUNCTION public.generate_case_summary TO hunter_app_user;
GRANT EXECUTE ON FUNCTION public.update_modified_column TO hunter_app_user;
GRANT EXECUTE ON FUNCTION public.cases_tsvector_update TO hunter_app_user;
GRANT EXECUTE ON FUNCTION public.get_case_statistics TO hunter_app_user;
GRANT EXECUTE ON FUNCTION public.get_case_complexity TO hunter_app_user;

-- === 9. INITIAL DATA ===
INSERT INTO schema_version (version) VALUES (1);
INSERT INTO system_tasks (task_name, status, last_run_date, notes)
VALUES ('CHECK_MODEL_STALENESS', 'PENDING', NULL, 'Checks if the AI model needs to be retrained.'),
       ('RUN_DATA_BALANCER', 'PENDING', NULL, 'Checks if the ''not_a_case'' dataset is balanced against the case files.'),
       ('ARCHIVE_OLD_LEADS', 'PENDING', NULL, 'Future task to archive or delete very old, unreviewed leads from the acquisition_log.');


-- === 10. COMMENTS ===
-- Extensions.  Can't comment unless you're the owner.
-- COMMENT ON EXTENSION postgis IS 'Adds support for geographic objects, enabling spatial queries.';
-- COMMENT ON EXTENSION pg_trgm IS 'Adds support for trigram matching, enabling fast, typo-tolerant "fuzzy" text search.';

-- Functions
COMMENT ON FUNCTION update_modified_column() IS 'A reusable trigger function to automatically update a modified_date column to the current timestamp.';
COMMENT ON FUNCTION get_nearby_cases IS 'Finds all cases within a given radius (in meters) of a specific lat/lon point.';
COMMENT ON FUNCTION cases_tsvector_update() IS 'A trigger function to automatically update the search vector when case content changes.';
COMMENT ON FUNCTION get_case_statistics IS 'Generates comprehensive statistics about cases in the system.';
COMMENT ON FUNCTION get_case_complexity IS 'Calculates a complexity score for a case based on its relationships and evidence.';
COMMENT ON FUNCTION perform_custom_maintenance IS 'Performs various maintenance tasks to keep the database healthy and efficient.';
COMMENT ON FUNCTION generate_case_summary IS 'Generates a complete, aggregated JSON summary for a single case, including its content, media, and investigation links.';

-- Tables and columns
  -- source_domains
COMMENT ON TABLE source_domains IS 'Master grimoire for platforms we hunt on. Stores global rules like rate limits and agent types.';
COMMENT ON COLUMN source_domains.agent_type IS 'The name of the search_agent script that handles this domain (e.g., ''reddit'', ''gnews_io'').';
COMMENT ON COLUMN source_domains.max_concurrent_requests IS 'The number of parallel workers allowed for this domain, acting as a semaphore limit.';

  -- sources
COMMENT ON TABLE sources IS 'The mission board. Each row is a specific, targeted hunt (e.g., a specific subreddit or search query).';
COMMENT ON COLUMN sources.target IS 'The specific target for the agent (e.g., a subreddit name, a search phrase).';
COMMENT ON COLUMN sources.purpose IS 'Defines if a source is for real-time ''lead_generation'' or long-term ''training_material''.';
COMMENT ON COLUMN sources.last_known_item_id IS 'The unique ID of the last item processed, used for efficient polling (the "high-water mark").';

  -- acquisition_log
COMMENT ON TABLE acquisition_log IS 'The master gate logbook. Tracks every single item an agent has ever encountered to prevent reprocessing.';
COMMENT ON COLUMN acquisition_log.item_url IS 'The universal fingerprint. Can be a URL, an RSS GUID, etc. The agent is responsible for providing the most stable unique ID available.';
COMMENT ON COLUMN acquisition_log.status IS 'The final disposition of the item: PROCESSED, IGNORED, or FAILED.';

  -- cases
COMMENT ON TABLE cases IS 'The "hot" metadata table for cases. Contains small, frequently searched columns for high-performance querying.';
COMMENT ON COLUMN cases.public_uuid IS 'A stable, public-facing unique identifier (UUID) for the case.';
COMMENT ON COLUMN cases.publication_date IS 'The original publication date of the source lead, used for freshness scoring.';
COMMENT ON COLUMN cases.severity_score IS 'A score (0.0-1.0) representing the AI-assessed severity of the case. NULL if not yet analyzed.';
COMMENT ON COLUMN cases.location_geom IS 'The primary geographic coordinate (Point) of the case, for PostGIS spatial queries.';

  -- case_content
COMMENT ON TABLE case_content IS 'The "cold" storage table for large text blobs associated with a case. Normalized for performance.';
COMMENT ON COLUMN case_content.search_vector IS 'A pre-processed tsvector for fast Full-Text Search, combining title and full_text.';

  -- media_evidernce
COMMENT ON TABLE media_evidence IS 'The evidence locker for all non-textual intel (images, audio, maps).';
COMMENT ON COLUMN media_evidence.location_type IS 'Enum-style field indicating if the evidence location is LOCAL, REMOTE, or ARCHIVED.';
COMMENT ON COLUMN media_evidence.thumbnail_path IS 'A local file path to a small, pre-generated thumbnail for fast GUI previews.';
COMMENT ON COLUMN media_evidence.location_geom IS 'The precise geographic coordinate where a piece of evidence was captured, for fine-grained spatial analysis.';

  -- investigations
COMMENT ON TABLE investigations IS 'The master list of all hunter investigations or theories (the "cork boards").';
COMMENT ON COLUMN investigations.parent_version_id IS 'Foreign key to itself, enabling versioning and hypothesis branching.';

  -- investigation_nodes
COMMENT ON TABLE investigation_nodes IS 'Represents a single item (a case, a piece of evidence, a note) pinned to an investigation board.';
COMMENT ON COLUMN investigation_nodes.pos_x IS 'The X/Y coordinates for this node on a future graphical UI.';

  -- investigation_links
COMMENT ON TABLE investigation_links IS 'Represents a piece of red string connecting two nodes on an investigation board.';
COMMENT ON COLUMN investigation_links.description IS 'A hunter''s note explaining the reason for connecting two nodes (e.g., "Same M.O.", "Happened on same date").';

  -- model_metadata
COMMENT ON TABLE model_metadata IS 'The "birth certificate" for our trained AI models, used to track staleness.';
COMMENT ON COLUMN model_metadata.case_word_count IS 'The total word count of the ''case'' data the model was trained on, used for staleness checks.';
COMMENT ON COLUMN model_metadata.not_case_word_count IS 'The total word count of the ''not_a_case'' data the model was trained on, used for staleness checks.';

  -- processed_files_log
COMMENT ON TABLE processed_files_log IS 'Master journal for manually acquired local files (PDFs, etc.) to prevent reprocessing.';
COMMENT ON COLUMN processed_files_log.file_hash IS 'The SHA-256 hash of the original file, acting as its unique fingerprint.';
COMMENT ON COLUMN processed_files_log.canonical_metadata IS 'A flexible JSONB field for storing extracted, structured metadata (e.g., issue number, author, ISBN).';

  -- processed_file_outputs
COMMENT ON TABLE processed_file_outputs IS 'A manifest linking a processed file to all of its generated output text chunks.';

  -- system_tasks
COMMENT ON TABLE system_tasks IS 'The application''s internal startup and maintenance checklist.';
COMMENT ON COLUMN system_tasks.task_name IS 'The unique, programmatic name of the maintenance task.';
COMMENT ON COLUMN system_tasks.status IS 'The current state of the task, used by the application to know what needs to be run.';

  -- schema_version
COMMENT ON TABLE schema_version IS 'Stores the current version of the database schema.';

-- Views
COMMENT ON VIEW case_summaries IS 'A clean summary view of cases, indicating if they have media or are part of an investigation.';
COMMENT ON VIEW case_category_stats IS 'A pivoted summary view of case statistics, grouped by category.';
COMMENT ON VIEW active_investigations IS 'Shows all active investigations with their node and link counts.';
COMMENT ON VIEW investigation_complexity IS 'Provides metrics about the complexity of each investigation.';

-- Reset search path
SET search_path = public;