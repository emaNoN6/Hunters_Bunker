--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg110+1)
-- Dumped by pg_dump version 17.3

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: almanac; Type: SCHEMA; Schema: -; Owner: hunter_admin
--

CREATE SCHEMA almanac;


ALTER SCHEMA almanac OWNER TO hunter_admin;

--
-- Name: acquisition_status; Type: TYPE; Schema: almanac; Owner: hunter_admin
--

CREATE TYPE almanac.acquisition_status AS ENUM (
    'NEW',
    'PROCESSED',
    'SKIPPED',
    'ERROR',
    'IGNORED'
);


ALTER TYPE almanac.acquisition_status OWNER TO hunter_admin;

--
-- Name: case_status; Type: TYPE; Schema: almanac; Owner: hunter_admin
--

CREATE TYPE almanac.case_status AS ENUM (
    'NEW',
    'TRIAGED',
    'ACTIVE',
    'CLOSED'
);


ALTER TYPE almanac.case_status OWNER TO hunter_admin;

--
-- Name: investigation_status; Type: TYPE; Schema: almanac; Owner: hunter_admin
--

CREATE TYPE almanac.investigation_status AS ENUM (
    'ACTIVE',
    'PAUSED',
    'ARCHIVED',
    'COLD_CASE'
);


ALTER TYPE almanac.investigation_status OWNER TO hunter_admin;

--
-- Name: lead_status; Type: TYPE; Schema: almanac; Owner: hunter_admin
--

CREATE TYPE almanac.lead_status AS ENUM (
    'NEW',
    'REVIEWING',
    'IGNORED',
    'PROMOTED'
);


ALTER TYPE almanac.lead_status OWNER TO hunter_admin;

--
-- Name: media_location_type; Type: TYPE; Schema: almanac; Owner: hunter_admin
--

CREATE TYPE almanac.media_location_type AS ENUM (
    'LOCAL',
    'REMOTE',
    'ARCHIVED'
);


ALTER TYPE almanac.media_location_type OWNER TO hunter_admin;

--
-- Name: node_type; Type: TYPE; Schema: almanac; Owner: hunter_admin
--

CREATE TYPE almanac.node_type AS ENUM (
    'CASE',
    'MEDIA',
    'NOTE'
);


ALTER TYPE almanac.node_type OWNER TO hunter_admin;

--
-- Name: cases_tsvector_update(); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.cases_tsvector_update() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION almanac.cases_tsvector_update() OWNER TO hunter_admin;

--
-- Name: generate_case_summary(bigint); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.generate_case_summary(p_case_id bigint) RETURNS json
    LANGUAGE plpgsql
    AS $$
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


ALTER FUNCTION almanac.generate_case_summary(p_case_id bigint) OWNER TO hunter_admin;

--
-- Name: FUNCTION generate_case_summary(p_case_id bigint); Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON FUNCTION almanac.generate_case_summary(p_case_id bigint) IS 'Generates a complete, aggregated JSON summary for a single case, including its content, media, and investigation links.';


--
-- Name: get_case_complexity(bigint); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.get_case_complexity(p_case_id bigint) RETURNS TABLE(case_title text, media_count bigint, investigation_references bigint, linked_cases bigint, complexity_score numeric)
    LANGUAGE plpgsql
    AS $$
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


ALTER FUNCTION almanac.get_case_complexity(p_case_id bigint) OWNER TO hunter_admin;

--
-- Name: FUNCTION get_case_complexity(p_case_id bigint); Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON FUNCTION almanac.get_case_complexity(p_case_id bigint) IS 'Calculates a complexity score for a case based on its relationships and evidence.';


--
-- Name: get_case_statistics(); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.get_case_statistics() RETURNS TABLE(total_cases bigint, cases_with_location bigint, cases_by_status json, avg_severity numeric, cases_last_24h bigint)
    LANGUAGE plpgsql
    AS $$
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


ALTER FUNCTION almanac.get_case_statistics() OWNER TO hunter_admin;

--
-- Name: FUNCTION get_case_statistics(); Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON FUNCTION almanac.get_case_statistics() IS 'Generates comprehensive statistics about cases in the system.';


--
-- Name: get_nearby_cases(double precision, double precision, double precision); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.get_nearby_cases(lat double precision, lon double precision, radius_meters double precision) RETURNS TABLE(id bigint, title text, distance_meters double precision)
    LANGUAGE plpgsql
    AS $$
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
$$;


ALTER FUNCTION almanac.get_nearby_cases(lat double precision, lon double precision, radius_meters double precision) OWNER TO hunter_admin;

--
-- Name: perform_custom_maintenance(); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.perform_custom_maintenance() RETURNS TABLE(maintenance_task text, result text)
    LANGUAGE plpgsql
    AS $$
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


ALTER FUNCTION almanac.perform_custom_maintenance() OWNER TO hunter_admin;

--
-- Name: FUNCTION perform_custom_maintenance(); Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON FUNCTION almanac.perform_custom_maintenance() IS 'Performs various maintenance tasks to keep the database healthy and efficient.';


--
-- Name: search_cds(text, almanac.lead_status, timestamp with time zone, timestamp with time zone); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.search_cds(p_search_term text, p_status almanac.lead_status DEFAULT NULL::almanac.lead_status, p_created_after timestamp with time zone DEFAULT NULL::timestamp with time zone, p_created_before timestamp with time zone DEFAULT NULL::timestamp with time zone) RETURNS TABLE(id bigint, uuid uuid, title text, url text, snippet text, rank real, match_type text, source_name text, domain_name text, status text, publication_date timestamp with time zone)
    LANGUAGE plpgsql STABLE
    AS $$
BEGIN
	RETURN QUERY
		WITH term_expansion AS (
			SELECT synonym AS term
			FROM search_synonyms
			WHERE base_term = p_search_term
			UNION
			SELECT derivation AS term
			FROM almanac.search_derivations
			WHERE base_term = p_search_term
			UNION
			SELECT p_search_term AS term
		),
		     compiled_search AS (
			     SELECT STRING_AGG(
					            '(' || REGEXP_REPLACE(TRIM(term), '\s+', ' <-> ', 'g') || ')',
					            ' | '
			            ) AS query_str
			     FROM term_expansion
			     WHERE term IS NOT NULL AND term <> ''
		     ),
		     ranked_results AS (
			     SELECT
				     cds.uuid,
				     cds.title,
				     (cds.metadata->>'article_url')::TEXT AS article_url,
				     TS_HEADLINE('english', cds.full_text,
				                 TO_TSQUERY('english', (SELECT query_str FROM compiled_search))
				     ) AS snippet,
				     TS_RANK(cds.fts_vector,
				             TO_TSQUERY('english', (SELECT query_str FROM compiled_search))
				     ) AS result_rank,
				     CASE
					     WHEN cds.fts_vector @@ TO_TSQUERY('english', p_search_term) THEN 'Exact Match'
					     ELSE 'Related Match'
					     END AS match_type,
				     s.source_name,
				     sd.domain_name,
				     ar.status,
				     ar.publication_date
			     FROM almanac.case_data_staging cds
			          JOIN almanac.acquisition_router ar ON cds.uuid = ar.lead_uuid
			          JOIN almanac.sources s ON ar.source_id = s.id
			          JOIN almanac.source_domains sd ON s.domain_id = sd.id
			     WHERE
				     cds.fts_vector @@ TO_TSQUERY('english', (SELECT query_str FROM compiled_search))
				   AND (p_status IS NULL OR ar.status = p_status)
				   AND (p_created_after IS NULL OR ar.publication_date >= p_created_after)
				   AND (p_created_before IS NULL OR ar.publication_date <= p_created_before)
		     )
		SELECT
					ROW_NUMBER() OVER (
				ORDER BY
					CASE WHEN rr.match_type = 'Exact Match' THEN 0 ELSE 1 END,
					result_rank DESC
				)::BIGINT AS id,
					rr.uuid,
					rr.title,
					rr.article_url,
					rr.snippet,
					rr.result_rank::REAL AS rank,
					rr.match_type,
					rr.source_name,
					rr.domain_name,
					rr.status::TEXT,  -- Cast ENUM to TEXT for return
					rr.publication_date
		FROM ranked_results rr
		ORDER BY
			CASE WHEN rr.match_type = 'Exact Match' THEN 0 ELSE 1 END,
			rr.result_rank DESC
		LIMIT 500;
END;
$$;


ALTER FUNCTION almanac.search_cds(p_search_term text, p_status almanac.lead_status, p_created_after timestamp with time zone, p_created_before timestamp with time zone) OWNER TO hunter_admin;

--
-- Name: touch_modified(); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.touch_modified() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.modified_date = now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION almanac.touch_modified() OWNER TO hunter_admin;

--
-- Name: update_router_partition_month(); Type: FUNCTION; Schema: almanac; Owner: hunter_admin
--

CREATE FUNCTION almanac.update_router_partition_month() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.partition_month := date_trunc('month', coalesce(NEW.last_seen_at, now()))::date;
    RETURN NEW;
END
$$;


ALTER FUNCTION almanac.update_router_partition_month() OWNER TO hunter_admin;

SET default_tablespace = '';

--
-- Name: acquisition_log; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
)
PARTITION BY RANGE (seen_at);


ALTER TABLE almanac.acquisition_log OWNER TO hunter_admin;

SET default_table_access_method = heap;

--
-- Name: acquisition_log_default; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_default (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_default OWNER TO hunter_admin;

--
-- Name: acquisition_log_id_seq1; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.acquisition_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.acquisition_log_id_seq1
    START WITH 210
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: acquisition_log_p20250801; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20250801 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20250801 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20250901; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20250901 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20250901 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20251001; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20251001 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20251001 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20251101; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20251101 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20251101 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20251201; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20251201 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20251201 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20260101; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20260101 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20260101 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20260201; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20260201 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20260201 OWNER TO hunter_admin;

--
-- Name: acquisition_log_p20260301; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_p20260301 (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_p20260301 OWNER TO hunter_admin;

--
-- Name: acquisition_log_template; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_log_template (
    id bigint NOT NULL,
    lead_uuid uuid NOT NULL,
    source_id bigint,
    seen_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE almanac.acquisition_log_template OWNER TO hunter_admin;

--
-- Name: acquisition_log_template_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.acquisition_log_template ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.acquisition_log_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: acquisition_router; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.acquisition_router (
    lead_uuid uuid NOT NULL,
    partition_month date NOT NULL,
    source_id bigint,
    item_url text,
    first_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    last_seen_at timestamp with time zone DEFAULT now() NOT NULL,
    publication_date timestamp with time zone,
    status almanac.lead_status DEFAULT 'NEW'::almanac.lead_status NOT NULL,
    id bigint NOT NULL
);


ALTER TABLE almanac.acquisition_router OWNER TO hunter_admin;

--
-- Name: acquisition_router_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.acquisition_router ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.acquisition_router_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: active_investigations; Type: VIEW; Schema: almanac; Owner: hunter_admin
--

CREATE VIEW almanac.active_investigations AS
SELECT
    NULL::bigint AS id,
    NULL::uuid AS public_uuid,
    NULL::text AS name,
    NULL::almanac.investigation_status AS status,
    NULL::text AS summary,
    NULL::integer AS version,
    NULL::integer AS parent_version_id,
    NULL::timestamp with time zone AS created_date,
    NULL::timestamp with time zone AS modified_date,
    NULL::bigint AS total_nodes,
    NULL::bigint AS total_links,
    NULL::timestamp with time zone AS last_activity;


ALTER VIEW almanac.active_investigations OWNER TO hunter_admin;

--
-- Name: VIEW active_investigations; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON VIEW almanac.active_investigations IS 'Shows all active investigations with their node and link counts.';


--
-- Name: api_usage_log; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.api_usage_log (
    id bigint NOT NULL,
    service text NOT NULL,
    endpoint text,
    word_queried text,
    called_at timestamp with time zone DEFAULT now(),
    response_code integer,
    rate_limit_remaining integer,
    rate_limit_limit integer,
    rate_limit_reset integer
);


ALTER TABLE almanac.api_usage_log OWNER TO hunter_admin;

--
-- Name: api_usage_log_id_seq1; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.api_usage_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.api_usage_log_id_seq1
    START WITH 444
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: assets; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.assets (
    asset_id uuid DEFAULT gen_random_uuid() NOT NULL,
    file_path text NOT NULL,
    file_type text DEFAULT 'unknown'::text,
    mime_type text,
    file_size bigint,
    created_at timestamp with time zone DEFAULT now(),
    source_type text,
    source_uuid uuid,
    original_url text,
    related_cases uuid[],
    related_investigations uuid[],
    is_enhanced jsonb,
    notes text,
    metadata jsonb,
    id bigint NOT NULL,
    CONSTRAINT assets_file_type_check CHECK ((file_type = ANY (ARRAY['image'::text, 'video'::text, 'audio'::text, 'document'::text, 'unknown'::text]))),
    CONSTRAINT assets_source_type_check CHECK ((source_type = ANY (ARRAY['lead'::text, 'case'::text, 'investigation'::text, 'manual'::text])))
);


ALTER TABLE almanac.assets OWNER TO hunter_admin;

--
-- Name: TABLE assets; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.assets IS 'Stores media and document files related to cases and investigations';


--
-- Name: COLUMN assets.file_path; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.assets.file_path IS 'Relative path within the assets folder';


--
-- Name: COLUMN assets.source_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.assets.source_uuid IS 'Loose reference to originating lead/case/investigation (no FK constraint)';


--
-- Name: COLUMN assets.related_cases; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.assets.related_cases IS 'Array of case UUIDs this asset is associated with';


--
-- Name: COLUMN assets.metadata; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.assets.metadata IS 'Structured JSON with processing, case_roles, and analysis data';


--
-- Name: assets_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.assets ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.assets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cases; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
)
PARTITION BY RANGE (publication_date);


ALTER TABLE almanac.cases OWNER TO hunter_admin;

--
-- Name: TABLE cases; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.cases IS 'Holds the metadata for a case, including its status and publication date.';


--
-- Name: COLUMN cases.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.title IS 'The title of the case.';


--
-- Name: COLUMN cases.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.url IS 'The URL of the case.';


--
-- Name: COLUMN cases.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.status IS 'The status of the case.';


--
-- Name: COLUMN cases.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.category IS 'The category of the case.';


--
-- Name: COLUMN cases.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: COLUMN cases.source_id; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases.source_id IS 'The ID linked to the sources table of the source that this case came from.';


--
-- Name: case_category_stats; Type: VIEW; Schema: almanac; Owner: hunter_admin
--

CREATE VIEW almanac.case_category_stats AS
 SELECT category,
    count(*) AS total_cases,
    count(*) FILTER (WHERE (status = 'NEW'::almanac.case_status)) AS new_cases,
    count(*) FILTER (WHERE (status = 'ACTIVE'::almanac.case_status)) AS active_cases,
    (avg(severity_score))::numeric(10,2) AS avg_severity
   FROM almanac.cases c
  WHERE (category IS NOT NULL)
  GROUP BY category;


ALTER VIEW almanac.case_category_stats OWNER TO hunter_admin;

--
-- Name: VIEW case_category_stats; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON VIEW almanac.case_category_stats IS 'A pivoted summary view of case statistics, grouped by category.';


--
-- Name: case_content; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
)
PARTITION BY RANGE (publication_date);


ALTER TABLE almanac.case_content OWNER TO hunter_admin;

--
-- Name: TABLE case_content; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.case_content IS 'Holds the full text of a case, including full HTML.';


--
-- Name: COLUMN case_content.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_default; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_default (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_default OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_default.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_default.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_default.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_default.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_default.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_default.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.case_content ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.case_content_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: case_content_p20250801; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20250801 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20250801 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20250801.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20250801.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20250801.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20250801.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20250801.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20250801.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20250901; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20250901 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20250901 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20250901.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20250901.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20250901.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20250901.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20250901.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20250901.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20251001; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20251001 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20251001 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20251001.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251001.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20251001.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251001.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20251001.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251001.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20251101; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20251101 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20251101 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20251101.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251101.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20251101.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251101.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20251101.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251101.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20251201; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20251201 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20251201 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20251201.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251201.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20251201.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251201.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20251201.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20251201.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20260101; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20260101 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20260101 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20260101.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260101.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20260101.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260101.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20260101.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260101.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20260201; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20260201 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20260201 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20260201.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260201.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20260201.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260201.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20260201.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260201.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_p20260301; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_p20260301 (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_p20260301 OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_p20260301.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260301.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_p20260301.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260301.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_p20260301.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_p20260301.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_template; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_content_template (
    case_id bigint NOT NULL,
    lead_uuid uuid,
    publication_date timestamp with time zone NOT NULL,
    full_text text,
    full_html text,
    search_vector tsvector,
    id bigint NOT NULL
);


ALTER TABLE almanac.case_content_template OWNER TO hunter_admin;

--
-- Name: COLUMN case_content_template.lead_uuid; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_template.lead_uuid IS 'The UUID of the lead that owns this case.';


--
-- Name: COLUMN case_content_template.full_text; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_template.full_text IS 'The full text of the case, without HTML.';


--
-- Name: COLUMN case_content_template.full_html; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.case_content_template.full_html IS 'The full text of the case, with HTML.';


--
-- Name: case_content_template_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.case_content_template ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.case_content_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: case_data_staging; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.case_data_staging (
    id bigint NOT NULL,
    uuid uuid NOT NULL,
    title text NOT NULL,
    full_text text NOT NULL,
    full_html text,
    metadata jsonb,
    fts_vector tsvector GENERATED ALWAYS AS ((setweight(to_tsvector('english'::regconfig, COALESCE(title, ''::text)), 'A'::"char") || setweight(to_tsvector('english'::regconfig, COALESCE(full_text, ''::text)), 'B'::"char"))) STORED
);


ALTER TABLE almanac.case_data_staging OWNER TO hunter_admin;

--
-- Name: TABLE case_data_staging; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.case_data_staging IS 'Holding table for freshly acquired case data';


--
-- Name: case_data_staging_id_seq1; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.case_data_staging ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.case_data_staging_id_seq1
    START WITH 2696
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: investigation_nodes; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.investigation_nodes (
    id bigint NOT NULL,
    investigation_id bigint NOT NULL,
    node_type almanac.node_type NOT NULL,
    node_id bigint,
    pos_x integer DEFAULT 0,
    pos_y integer DEFAULT 0,
    note_text text
);


ALTER TABLE almanac.investigation_nodes OWNER TO hunter_admin;

--
-- Name: media_evidence; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.media_evidence (
    id integer NOT NULL,
    public_uuid uuid NOT NULL,
    case_id bigint NOT NULL,
    case_publication_date timestamp with time zone NOT NULL,
    location text NOT NULL,
    location_type text NOT NULL,
    thumbnail_path text,
    description text,
    evidence_type text,
    location_geom public.geometry(Point,4326),
    CONSTRAINT media_evidence_location_type_check CHECK ((upper(location_type) = ANY (ARRAY['LOCAL'::text, 'REMOTE'::text, 'ARCHIVED'::text])))
);


ALTER TABLE almanac.media_evidence OWNER TO hunter_admin;

--
-- Name: TABLE media_evidence; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.media_evidence IS 'The evidence locker for all non-textual intel (images, audio, maps).';


--
-- Name: COLUMN media_evidence.location_type; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.media_evidence.location_type IS 'Enum-style field indicating if the evidence location is LOCAL, REMOTE, or ARCHIVED.';


--
-- Name: COLUMN media_evidence.thumbnail_path; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.media_evidence.thumbnail_path IS 'A local file path to a small, pre-generated thumbnail for fast GUI previews.';


--
-- Name: COLUMN media_evidence.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.media_evidence.location_geom IS 'The precise geographic coordinate where a piece of evidence was captured, for fine-grained spatial analysis.';


--
-- Name: case_summaries; Type: VIEW; Schema: almanac; Owner: hunter_admin
--

CREATE VIEW almanac.case_summaries AS
 SELECT id,
    public_uuid,
    title,
    status,
    category,
    severity_score,
    publication_date,
    modified_date,
    (EXISTS ( SELECT 1
           FROM almanac.media_evidence me
          WHERE (me.case_id = c.id))) AS has_media,
    (EXISTS ( SELECT 1
           FROM almanac.investigation_nodes n
          WHERE ((n.node_type = 'CASE'::almanac.node_type) AND (n.node_id = c.id)))) AS in_investigation
   FROM almanac.cases c;


ALTER VIEW almanac.case_summaries OWNER TO hunter_admin;

--
-- Name: VIEW case_summaries; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON VIEW almanac.case_summaries IS 'A clean summary view of cases, indicating if they have media or are part of an investigation.';


--
-- Name: cases_default; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_default (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_default OWNER TO hunter_admin;

--
-- Name: COLUMN cases_default.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.title IS 'The title of the case.';


--
-- Name: COLUMN cases_default.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_default.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_default.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_default.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_default.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.status IS 'The status of the case.';


--
-- Name: COLUMN cases_default.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.category IS 'The category of the case.';


--
-- Name: COLUMN cases_default.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_default.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_default.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: cases_id_seq1; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.cases ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.cases_id_seq1
    START WITH 26
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: cases_p20250801; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20250801 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20250801 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20250801.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20250801.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20250801.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20250801.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20250801.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20250801.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20250801.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20250801.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20250801.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250801.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: cases_p20250901; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20250901 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20250901 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20250901.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20250901.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20250901.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20250901.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20250901.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20250901.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20250901.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20250901.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20250901.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20250901.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: cases_p20251001; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20251001 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20251001 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20251001.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20251001.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20251001.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20251001.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20251001.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20251001.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20251001.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20251001.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20251001.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251001.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: cases_p20251101; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20251101 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20251101 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20251101.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20251101.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20251101.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20251101.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20251101.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20251101.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20251101.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20251101.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20251101.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251101.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: cases_p20251201; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20251201 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20251201 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20251201.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20251201.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20251201.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20251201.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20251201.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20251201.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20251201.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20251201.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20251201.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: COLUMN cases_p20251201.source_id; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20251201.source_id IS 'The ID linked to the sources table of the source that this case came from.';


--
-- Name: cases_p20260101; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20260101 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20260101 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20260101.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20260101.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20260101.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20260101.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20260101.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20260101.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20260101.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20260101.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20260101.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: COLUMN cases_p20260101.source_id; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260101.source_id IS 'The ID linked to the sources table of the source that this case came from.';


--
-- Name: cases_p20260201; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20260201 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20260201 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20260201.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20260201.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20260201.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20260201.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20260201.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20260201.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20260201.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20260201.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20260201.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: COLUMN cases_p20260201.source_id; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260201.source_id IS 'The ID linked to the sources table of the source that this case came from.';


--
-- Name: cases_p20260301; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_p20260301 (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326),
    source_name text,
    source_id bigint
);


ALTER TABLE almanac.cases_p20260301 OWNER TO hunter_admin;

--
-- Name: COLUMN cases_p20260301.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.title IS 'The title of the case.';


--
-- Name: COLUMN cases_p20260301.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_p20260301.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_p20260301.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_p20260301.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_p20260301.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.status IS 'The status of the case.';


--
-- Name: COLUMN cases_p20260301.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.category IS 'The category of the case.';


--
-- Name: COLUMN cases_p20260301.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_p20260301.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: COLUMN cases_p20260301.source_id; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_p20260301.source_id IS 'The ID linked to the sources table of the source that this case came from.';


--
-- Name: cases_template; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.cases_template (
    id bigint NOT NULL,
    lead_uuid uuid,
    public_uuid uuid DEFAULT gen_random_uuid(),
    title text NOT NULL,
    url text NOT NULL,
    publication_date timestamp with time zone NOT NULL,
    modified_date timestamp with time zone DEFAULT now() NOT NULL,
    triage_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    status almanac.case_status DEFAULT 'NEW'::almanac.case_status NOT NULL,
    category text,
    severity_score numeric(10,2),
    location_geom public.geometry(Point,4326)
);


ALTER TABLE almanac.cases_template OWNER TO hunter_admin;

--
-- Name: COLUMN cases_template.title; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.title IS 'The title of the case.';


--
-- Name: COLUMN cases_template.url; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.url IS 'The URL of the case.';


--
-- Name: COLUMN cases_template.publication_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.publication_date IS 'The publication date of the case.';


--
-- Name: COLUMN cases_template.modified_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.modified_date IS 'The date the case was last modified.';


--
-- Name: COLUMN cases_template.triage_date; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.triage_date IS 'The date the case was triaged.';


--
-- Name: COLUMN cases_template.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.status IS 'The status of the case.';


--
-- Name: COLUMN cases_template.category; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.category IS 'The category of the case.';


--
-- Name: COLUMN cases_template.severity_score; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.severity_score IS 'The severity score of the case from 0.0 to 1.0.';


--
-- Name: COLUMN cases_template.location_geom; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.cases_template.location_geom IS 'The location of the case, as a geometry.';


--
-- Name: cases_template_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.cases_template ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.cases_template_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: source_domains; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.source_domains (
    id bigint NOT NULL,
    domain_name text NOT NULL,
    agent_type text NOT NULL,
    max_concurrent_requests integer DEFAULT 1 NOT NULL,
    api_endpoint text,
    notes text,
    has_standard_foreman boolean DEFAULT false NOT NULL
);


ALTER TABLE almanac.source_domains OWNER TO hunter_admin;

--
-- Name: COLUMN source_domains.has_standard_foreman; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.source_domains.has_standard_foreman IS 'If TRUE, the dispatcher will expect a corresponding foreman file to exist.';


--
-- Name: foreman_agents; Type: VIEW; Schema: almanac; Owner: hunter_admin
--

CREATE VIEW almanac.foreman_agents AS
 SELECT DISTINCT (agent_type || '_foreman'::text) AS agent_type
   FROM almanac.source_domains
  WHERE (has_standard_foreman IS TRUE);


ALTER VIEW almanac.foreman_agents OWNER TO hunter_admin;

--
-- Name: investigation_links; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.investigation_links (
    id bigint NOT NULL,
    investigation_id bigint NOT NULL,
    node_a_id bigint NOT NULL,
    node_b_id bigint NOT NULL,
    node_min_id bigint GENERATED ALWAYS AS (LEAST(node_a_id, node_b_id)) STORED,
    node_max_id bigint GENERATED ALWAYS AS (GREATEST(node_a_id, node_b_id)) STORED,
    CONSTRAINT chk_no_self_link CHECK ((node_a_id <> node_b_id))
);


ALTER TABLE almanac.investigation_links OWNER TO hunter_admin;

--
-- Name: investigations; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.investigations (
    id bigint NOT NULL,
    public_uuid uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    status almanac.investigation_status DEFAULT 'ACTIVE'::almanac.investigation_status NOT NULL,
    summary text,
    version integer DEFAULT 1 NOT NULL,
    parent_version_id integer,
    created_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    modified_date timestamp with time zone DEFAULT now(),
    CONSTRAINT valid_version_check CHECK ((version > 0))
);


ALTER TABLE almanac.investigations OWNER TO hunter_admin;

--
-- Name: investigation_complexity; Type: VIEW; Schema: almanac; Owner: hunter_admin
--

CREATE VIEW almanac.investigation_complexity AS
 SELECT i.id,
    i.name,
    i.status,
    count(DISTINCT n.id) AS total_nodes,
    count(DISTINCT l.id) AS total_links,
    count(DISTINCT
        CASE
            WHEN (n.node_type = 'CASE'::almanac.node_type) THEN n.id
            ELSE NULL::bigint
        END) AS case_count,
    count(DISTINCT
        CASE
            WHEN (n.node_type = 'MEDIA'::almanac.node_type) THEN n.id
            ELSE NULL::bigint
        END) AS media_count,
    count(DISTINCT
        CASE
            WHEN (n.node_type = 'NOTE'::almanac.node_type) THEN n.id
            ELSE NULL::bigint
        END) AS note_count,
    (((count(DISTINCT l.id))::double precision / (NULLIF(count(DISTINCT n.id), 0))::double precision))::numeric(10,2) AS connectivity_ratio
   FROM ((almanac.investigations i
     LEFT JOIN almanac.investigation_nodes n ON ((i.id = n.investigation_id)))
     LEFT JOIN almanac.investigation_links l ON ((i.id = l.investigation_id)))
  GROUP BY i.id, i.name, i.status;


ALTER VIEW almanac.investigation_complexity OWNER TO hunter_admin;

--
-- Name: VIEW investigation_complexity; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON VIEW almanac.investigation_complexity IS 'Provides metrics about the complexity of each investigation.';


--
-- Name: investigation_links_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.investigation_links ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.investigation_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: investigation_nodes_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.investigation_nodes ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.investigation_nodes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: investigations_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.investigations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.investigations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: keyword_library; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.keyword_library (
    keyword text NOT NULL,
    theme text DEFAULT 'uncategorized'::text NOT NULL,
    id bigint NOT NULL
);


ALTER TABLE almanac.keyword_library OWNER TO hunter_admin;

--
-- Name: keyword_library_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.keyword_library ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.keyword_library_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: media_evidence_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.media_evidence ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.media_evidence_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: model_metadata; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.model_metadata (
    model_name text NOT NULL,
    train_date timestamp with time zone NOT NULL,
    case_word_count integer NOT NULL,
    not_case_word_count integer NOT NULL,
    categories text NOT NULL,
    id bigint NOT NULL
);


ALTER TABLE almanac.model_metadata OWNER TO hunter_admin;

--
-- Name: TABLE model_metadata; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.model_metadata IS 'The "birth certificate" for our trained AI models, used to track staleness.';


--
-- Name: COLUMN model_metadata.case_word_count; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.model_metadata.case_word_count IS 'The total word count of the ''case'' data the model was trained on, used for staleness checks.';


--
-- Name: COLUMN model_metadata.not_case_word_count; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.model_metadata.not_case_word_count IS 'The total word count of the ''not_a_case'' data the model was trained on, used for staleness checks.';


--
-- Name: model_metadata_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.model_metadata ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.model_metadata_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: processed_file_outputs; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.processed_file_outputs (
    id integer NOT NULL,
    parent_file_hash text NOT NULL,
    output_path text NOT NULL
);


ALTER TABLE almanac.processed_file_outputs OWNER TO hunter_admin;

--
-- Name: TABLE processed_file_outputs; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.processed_file_outputs IS 'A manifest linking a processed file to all of its generated output text chunks.';


--
-- Name: processed_file_outputs_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.processed_file_outputs ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.processed_file_outputs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: processed_files_log; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.processed_files_log (
    file_hash text NOT NULL,
    original_filename text NOT NULL,
    metadata_type text,
    canonical_metadata jsonb,
    processed_as_category text,
    process_date timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    id bigint NOT NULL
);


ALTER TABLE almanac.processed_files_log OWNER TO hunter_admin;

--
-- Name: TABLE processed_files_log; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.processed_files_log IS 'Master journal for manually acquired local files (PDFs, etc.) to prevent reprocessing.';


--
-- Name: COLUMN processed_files_log.file_hash; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.processed_files_log.file_hash IS 'The SHA-256 hash of the original file, acting as its unique fingerprint.';


--
-- Name: COLUMN processed_files_log.canonical_metadata; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.processed_files_log.canonical_metadata IS 'A flexible JSONB field for storing extracted, structured metadata (e.g., issue number, author, ISBN).';


--
-- Name: processed_files_log_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.processed_files_log ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.processed_files_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: schema_version; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.schema_version (
    version integer NOT NULL
);


ALTER TABLE almanac.schema_version OWNER TO hunter_admin;

--
-- Name: search_derivations; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.search_derivations (
    base_term text NOT NULL,
    derivation text NOT NULL,
    source text DEFAULT 'wordsapi'::text,
    id bigint NOT NULL
);


ALTER TABLE almanac.search_derivations OWNER TO hunter_admin;

--
-- Name: search_derivations_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.search_derivations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.search_derivations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: search_synonyms; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.search_synonyms (
    base_term text NOT NULL,
    synonym text NOT NULL,
    sense_index integer NOT NULL,
    definition_snippet text,
    id bigint NOT NULL
);


ALTER TABLE almanac.search_synonyms OWNER TO hunter_admin;

--
-- Name: search_synonyms_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.search_synonyms ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.search_synonyms_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: search_terms; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.search_terms (
    base_term text NOT NULL,
    api_response jsonb NOT NULL,
    last_updated timestamp with time zone DEFAULT now(),
    id bigint NOT NULL
);


ALTER TABLE almanac.search_terms OWNER TO hunter_admin;

--
-- Name: search_terms_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.search_terms ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.search_terms_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: source_domains_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.source_domains ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.source_domains_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sources; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.sources (
    id bigint NOT NULL,
    source_name text NOT NULL,
    domain_id bigint,
    consecutive_failures integer,
    last_success_date timestamp with time zone,
    last_failure_date timestamp with time zone,
    target text DEFAULT 'UNSET'::text NOT NULL,
    last_checked_date timestamp with time zone,
    strategy text,
    keywords text,
    is_active boolean DEFAULT true NOT NULL,
    purpose text DEFAULT 'lead_generation'::text NOT NULL,
    next_release_date timestamp with time zone,
    last_known_item_id text
);


ALTER TABLE almanac.sources OWNER TO hunter_admin;

--
-- Name: sources_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.sources ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.sources_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: system_tasks; Type: TABLE; Schema: almanac; Owner: hunter_admin
--

CREATE TABLE almanac.system_tasks (
    task_name text NOT NULL,
    status text NOT NULL,
    last_run_date timestamp with time zone,
    notes text,
    id bigint NOT NULL,
    CONSTRAINT system_tasks_status_check CHECK ((upper(status) = ANY (ARRAY['PENDING'::text, 'IN_PROGRESS'::text, 'COMPLETE'::text])))
);


ALTER TABLE almanac.system_tasks OWNER TO hunter_admin;

--
-- Name: TABLE system_tasks; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON TABLE almanac.system_tasks IS 'The application''s internal startup and maintenance checklist.';


--
-- Name: COLUMN system_tasks.task_name; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.system_tasks.task_name IS 'The unique, programmatic name of the maintenance task.';


--
-- Name: COLUMN system_tasks.status; Type: COMMENT; Schema: almanac; Owner: hunter_admin
--

COMMENT ON COLUMN almanac.system_tasks.status IS 'The current state of the task, used by the application to know what needs to be run.';


--
-- Name: system_tasks_id_seq; Type: SEQUENCE; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.system_tasks ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME almanac.system_tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: v_search_dictionary; Type: VIEW; Schema: almanac; Owner: hunter_admin
--

CREATE VIEW almanac.v_search_dictionary AS
 SELECT base_term,
    string_agg((('('::text || regexp_replace(TRIM(BOTH FROM term), '\s+'::text, ' <-> '::text, 'g'::text)) || ')'::text), ' | '::text) AS compiled_tsquery
   FROM ( SELECT search_synonyms.base_term,
            search_synonyms.synonym AS term
           FROM almanac.search_synonyms
        UNION
         SELECT search_derivations.base_term,
            search_derivations.derivation AS term
           FROM almanac.search_derivations
        UNION
         SELECT search_terms.base_term,
            search_terms.base_term AS term
           FROM almanac.search_terms) all_terms
  WHERE ((term IS NOT NULL) AND (term <> ''::text))
  GROUP BY base_term;


ALTER VIEW almanac.v_search_dictionary OWNER TO hunter_admin;

--
-- Name: acquisition_log_default; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_default DEFAULT;


--
-- Name: acquisition_log_p20250801; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20250801 FOR VALUES FROM ('2025-08-01 04:00:00+00') TO ('2025-09-01 04:00:00+00');


--
-- Name: acquisition_log_p20250901; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20250901 FOR VALUES FROM ('2025-09-01 04:00:00+00') TO ('2025-10-01 04:00:00+00');


--
-- Name: acquisition_log_p20251001; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20251001 FOR VALUES FROM ('2025-10-01 04:00:00+00') TO ('2025-11-01 04:00:00+00');


--
-- Name: acquisition_log_p20251101; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20251101 FOR VALUES FROM ('2025-11-01 04:00:00+00') TO ('2025-12-01 04:00:00+00');


--
-- Name: acquisition_log_p20251201; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20251201 FOR VALUES FROM ('2025-12-01 04:00:00+00') TO ('2026-01-01 04:00:00+00');


--
-- Name: acquisition_log_p20260101; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20260101 FOR VALUES FROM ('2026-01-01 04:00:00+00') TO ('2026-02-01 04:00:00+00');


--
-- Name: acquisition_log_p20260201; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20260201 FOR VALUES FROM ('2026-02-01 04:00:00+00') TO ('2026-03-01 04:00:00+00');


--
-- Name: acquisition_log_p20260301; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log ATTACH PARTITION almanac.acquisition_log_p20260301 FOR VALUES FROM ('2026-03-01 04:00:00+00') TO ('2026-04-01 04:00:00+00');


--
-- Name: case_content_default; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_default DEFAULT;


--
-- Name: case_content_p20250801; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20250801 FOR VALUES FROM ('2025-08-01 04:00:00+00') TO ('2025-09-01 04:00:00+00');


--
-- Name: case_content_p20250901; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20250901 FOR VALUES FROM ('2025-09-01 04:00:00+00') TO ('2025-10-01 04:00:00+00');


--
-- Name: case_content_p20251001; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20251001 FOR VALUES FROM ('2025-10-01 04:00:00+00') TO ('2025-11-01 04:00:00+00');


--
-- Name: case_content_p20251101; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20251101 FOR VALUES FROM ('2025-11-01 04:00:00+00') TO ('2025-12-01 04:00:00+00');


--
-- Name: case_content_p20251201; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20251201 FOR VALUES FROM ('2025-12-01 04:00:00+00') TO ('2026-01-01 04:00:00+00');


--
-- Name: case_content_p20260101; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20260101 FOR VALUES FROM ('2026-01-01 04:00:00+00') TO ('2026-02-01 04:00:00+00');


--
-- Name: case_content_p20260201; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20260201 FOR VALUES FROM ('2026-02-01 04:00:00+00') TO ('2026-03-01 04:00:00+00');


--
-- Name: case_content_p20260301; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content ATTACH PARTITION almanac.case_content_p20260301 FOR VALUES FROM ('2026-03-01 04:00:00+00') TO ('2026-04-01 04:00:00+00');


--
-- Name: cases_default; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_default DEFAULT;


--
-- Name: cases_p20250801; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20250801 FOR VALUES FROM ('2025-08-01 04:00:00+00') TO ('2025-09-01 04:00:00+00');


--
-- Name: cases_p20250901; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20250901 FOR VALUES FROM ('2025-09-01 04:00:00+00') TO ('2025-10-01 04:00:00+00');


--
-- Name: cases_p20251001; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20251001 FOR VALUES FROM ('2025-10-01 04:00:00+00') TO ('2025-11-01 04:00:00+00');


--
-- Name: cases_p20251101; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20251101 FOR VALUES FROM ('2025-11-01 04:00:00+00') TO ('2025-12-01 04:00:00+00');


--
-- Name: cases_p20251201; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20251201 FOR VALUES FROM ('2025-12-01 04:00:00+00') TO ('2026-01-01 04:00:00+00');


--
-- Name: cases_p20260101; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20260101 FOR VALUES FROM ('2026-01-01 04:00:00+00') TO ('2026-02-01 04:00:00+00');


--
-- Name: cases_p20260201; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20260201 FOR VALUES FROM ('2026-02-01 04:00:00+00') TO ('2026-03-01 04:00:00+00');


--
-- Name: cases_p20260301; Type: TABLE ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases ATTACH PARTITION almanac.cases_p20260301 FOR VALUES FROM ('2026-03-01 04:00:00+00') TO ('2026-04-01 04:00:00+00');


--
-- Name: acquisition_log acquisition_log_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log
    ADD CONSTRAINT acquisition_log_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_default acquisition_log_default_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_default
    ADD CONSTRAINT acquisition_log_default_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20250801 acquisition_log_p20250801_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20250801
    ADD CONSTRAINT acquisition_log_p20250801_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20250901 acquisition_log_p20250901_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20250901
    ADD CONSTRAINT acquisition_log_p20250901_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20251001 acquisition_log_p20251001_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20251001
    ADD CONSTRAINT acquisition_log_p20251001_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20251101 acquisition_log_p20251101_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20251101
    ADD CONSTRAINT acquisition_log_p20251101_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20251201 acquisition_log_p20251201_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20251201
    ADD CONSTRAINT acquisition_log_p20251201_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20260101 acquisition_log_p20260101_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20260101
    ADD CONSTRAINT acquisition_log_p20260101_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20260201 acquisition_log_p20260201_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20260201
    ADD CONSTRAINT acquisition_log_p20260201_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_p20260301 acquisition_log_p20260301_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_p20260301
    ADD CONSTRAINT acquisition_log_p20260301_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_log_template acquisition_log_template_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_log_template
    ADD CONSTRAINT acquisition_log_template_pkey PRIMARY KEY (id, seen_at);


--
-- Name: acquisition_router acquisition_router_item_url_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_router
    ADD CONSTRAINT acquisition_router_item_url_key UNIQUE (item_url);


--
-- Name: acquisition_router acquisition_router_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_router
    ADD CONSTRAINT acquisition_router_pkey PRIMARY KEY (lead_uuid);


--
-- Name: api_usage_log api_usage_log_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.api_usage_log
    ADD CONSTRAINT api_usage_log_pkey PRIMARY KEY (id);


--
-- Name: assets assets_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.assets
    ADD CONSTRAINT assets_pkey PRIMARY KEY (asset_id);


--
-- Name: case_content case_content_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content
    ADD CONSTRAINT case_content_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_default case_content_default_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_default
    ADD CONSTRAINT case_content_default_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20250801 case_content_p20250801_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20250801
    ADD CONSTRAINT case_content_p20250801_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20250901 case_content_p20250901_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20250901
    ADD CONSTRAINT case_content_p20250901_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20251001 case_content_p20251001_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20251001
    ADD CONSTRAINT case_content_p20251001_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20251101 case_content_p20251101_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20251101
    ADD CONSTRAINT case_content_p20251101_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20251201 case_content_p20251201_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20251201
    ADD CONSTRAINT case_content_p20251201_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20260101 case_content_p20260101_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20260101
    ADD CONSTRAINT case_content_p20260101_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20260201 case_content_p20260201_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20260201
    ADD CONSTRAINT case_content_p20260201_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_p20260301 case_content_p20260301_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_p20260301
    ADD CONSTRAINT case_content_p20260301_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_content_template case_content_template_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_content_template
    ADD CONSTRAINT case_content_template_pkey PRIMARY KEY (case_id, publication_date);


--
-- Name: case_data_staging case_data_staging_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_data_staging
    ADD CONSTRAINT case_data_staging_pkey PRIMARY KEY (id);


--
-- Name: case_data_staging case_data_staging_uuid_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_data_staging
    ADD CONSTRAINT case_data_staging_uuid_key UNIQUE (uuid);


--
-- Name: cases cases_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases
    ADD CONSTRAINT cases_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_default cases_default_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_default
    ADD CONSTRAINT cases_default_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases cases_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases
    ADD CONSTRAINT cases_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_default cases_default_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_default
    ADD CONSTRAINT cases_default_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20250801 cases_p20250801_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20250801
    ADD CONSTRAINT cases_p20250801_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20250801 cases_p20250801_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20250801
    ADD CONSTRAINT cases_p20250801_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20250901 cases_p20250901_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20250901
    ADD CONSTRAINT cases_p20250901_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20250901 cases_p20250901_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20250901
    ADD CONSTRAINT cases_p20250901_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20251001 cases_p20251001_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20251001
    ADD CONSTRAINT cases_p20251001_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20251001 cases_p20251001_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20251001
    ADD CONSTRAINT cases_p20251001_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20251101 cases_p20251101_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20251101
    ADD CONSTRAINT cases_p20251101_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20251101 cases_p20251101_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20251101
    ADD CONSTRAINT cases_p20251101_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20251201 cases_p20251201_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20251201
    ADD CONSTRAINT cases_p20251201_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20251201 cases_p20251201_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20251201
    ADD CONSTRAINT cases_p20251201_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20260101 cases_p20260101_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20260101
    ADD CONSTRAINT cases_p20260101_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20260101 cases_p20260101_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20260101
    ADD CONSTRAINT cases_p20260101_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20260201 cases_p20260201_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20260201
    ADD CONSTRAINT cases_p20260201_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20260201 cases_p20260201_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20260201
    ADD CONSTRAINT cases_p20260201_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_p20260301 cases_p20260301_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20260301
    ADD CONSTRAINT cases_p20260301_pkey PRIMARY KEY (id, publication_date);


--
-- Name: cases_p20260301 cases_p20260301_url_publication_date_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_p20260301
    ADD CONSTRAINT cases_p20260301_url_publication_date_key UNIQUE (url, publication_date);


--
-- Name: cases_template cases_template_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.cases_template
    ADD CONSTRAINT cases_template_pkey PRIMARY KEY (id, publication_date);


--
-- Name: investigation_links investigation_links_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_links
    ADD CONSTRAINT investigation_links_pkey PRIMARY KEY (id);


--
-- Name: investigation_nodes investigation_nodes_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_nodes
    ADD CONSTRAINT investigation_nodes_pkey PRIMARY KEY (id);


--
-- Name: investigations investigations_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigations
    ADD CONSTRAINT investigations_pkey PRIMARY KEY (id);


--
-- Name: investigations investigations_public_uuid_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigations
    ADD CONSTRAINT investigations_public_uuid_key UNIQUE (public_uuid);


--
-- Name: keyword_library keyword_library_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.keyword_library
    ADD CONSTRAINT keyword_library_pkey PRIMARY KEY (keyword, theme);


--
-- Name: media_evidence media_evidence_location_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.media_evidence
    ADD CONSTRAINT media_evidence_location_key UNIQUE (location);


--
-- Name: media_evidence media_evidence_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.media_evidence
    ADD CONSTRAINT media_evidence_pkey PRIMARY KEY (id);


--
-- Name: media_evidence media_evidence_public_uuid_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.media_evidence
    ADD CONSTRAINT media_evidence_public_uuid_key UNIQUE (public_uuid);


--
-- Name: model_metadata model_metadata_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.model_metadata
    ADD CONSTRAINT model_metadata_pkey PRIMARY KEY (model_name);


--
-- Name: processed_file_outputs processed_file_outputs_output_path_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.processed_file_outputs
    ADD CONSTRAINT processed_file_outputs_output_path_key UNIQUE (output_path);


--
-- Name: processed_file_outputs processed_file_outputs_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.processed_file_outputs
    ADD CONSTRAINT processed_file_outputs_pkey PRIMARY KEY (id);


--
-- Name: processed_files_log processed_files_log_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.processed_files_log
    ADD CONSTRAINT processed_files_log_pkey PRIMARY KEY (file_hash);


--
-- Name: search_derivations search_derivations_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.search_derivations
    ADD CONSTRAINT search_derivations_pkey PRIMARY KEY (base_term, derivation);


--
-- Name: search_synonyms search_synonyms_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.search_synonyms
    ADD CONSTRAINT search_synonyms_pkey PRIMARY KEY (base_term, synonym, sense_index);


--
-- Name: search_terms search_terms_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.search_terms
    ADD CONSTRAINT search_terms_pkey PRIMARY KEY (base_term);


--
-- Name: source_domains source_domains_domain_name_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.source_domains
    ADD CONSTRAINT source_domains_domain_name_key UNIQUE (domain_name);


--
-- Name: source_domains source_domains_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.source_domains
    ADD CONSTRAINT source_domains_pkey PRIMARY KEY (id);


--
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (id);


--
-- Name: sources sources_source_name_key; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.sources
    ADD CONSTRAINT sources_source_name_key UNIQUE (source_name);


--
-- Name: system_tasks system_tasks_pkey; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.system_tasks
    ADD CONSTRAINT system_tasks_pkey PRIMARY KEY (task_name);


--
-- Name: assets unique_file_path; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.assets
    ADD CONSTRAINT unique_file_path UNIQUE (file_path);


--
-- Name: investigation_links ux_investigation_edge_unique; Type: CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_links
    ADD CONSTRAINT ux_investigation_edge_unique UNIQUE (investigation_id, node_min_id, node_max_id);


--
-- Name: idx_acq_lead_uuid; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_acq_lead_uuid ON ONLY almanac.acquisition_log USING btree (lead_uuid);


--
-- Name: acquisition_log_default_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_default_lead_uuid_idx ON almanac.acquisition_log_default USING btree (lead_uuid);


--
-- Name: acquisition_log_p20250801_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20250801_lead_uuid_idx ON almanac.acquisition_log_p20250801 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20250901_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20250901_lead_uuid_idx ON almanac.acquisition_log_p20250901 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20251001_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20251001_lead_uuid_idx ON almanac.acquisition_log_p20251001 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20251101_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20251101_lead_uuid_idx ON almanac.acquisition_log_p20251101 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20251201_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20251201_lead_uuid_idx ON almanac.acquisition_log_p20251201 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20260101_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20260101_lead_uuid_idx ON almanac.acquisition_log_p20260101 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20260201_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20260201_lead_uuid_idx ON almanac.acquisition_log_p20260201 USING btree (lead_uuid);


--
-- Name: acquisition_log_p20260301_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_p20260301_lead_uuid_idx ON almanac.acquisition_log_p20260301 USING btree (lead_uuid);


--
-- Name: acquisition_log_template_brin_seen; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_template_brin_seen ON almanac.acquisition_log_template USING brin (seen_at) WITH (pages_per_range='64');


--
-- Name: acquisition_log_template_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_log_template_lead_uuid_idx ON almanac.acquisition_log_template USING btree (lead_uuid);


--
-- Name: acquisition_router_source_id_index; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX acquisition_router_source_id_index ON almanac.acquisition_router USING btree (source_id);


--
-- Name: idx_case_content_tsv; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_case_content_tsv ON ONLY almanac.case_content USING gin (search_vector);


--
-- Name: case_content_default_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_default_search_vector_idx ON almanac.case_content_default USING gin (search_vector);


--
-- Name: case_content_p20250801_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20250801_search_vector_idx ON almanac.case_content_p20250801 USING gin (search_vector);


--
-- Name: case_content_p20250901_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20250901_search_vector_idx ON almanac.case_content_p20250901 USING gin (search_vector);


--
-- Name: case_content_p20251001_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20251001_search_vector_idx ON almanac.case_content_p20251001 USING gin (search_vector);


--
-- Name: case_content_p20251101_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20251101_search_vector_idx ON almanac.case_content_p20251101 USING gin (search_vector);


--
-- Name: case_content_p20251201_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20251201_search_vector_idx ON almanac.case_content_p20251201 USING gin (search_vector);


--
-- Name: case_content_p20260101_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20260101_search_vector_idx ON almanac.case_content_p20260101 USING gin (search_vector);


--
-- Name: case_content_p20260201_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20260201_search_vector_idx ON almanac.case_content_p20260201 USING gin (search_vector);


--
-- Name: case_content_p20260301_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_p20260301_search_vector_idx ON almanac.case_content_p20260301 USING gin (search_vector);


--
-- Name: case_content_template_case_id; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_template_case_id ON almanac.case_content_template USING btree (case_id);


--
-- Name: case_content_template_search_vector_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_template_search_vector_idx ON almanac.case_content_template USING gin (search_vector);


--
-- Name: case_content_template_tsv; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_content_template_tsv ON almanac.case_content_template USING gin (search_vector);


--
-- Name: case_data_staging_full_text_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_data_staging_full_text_idx ON almanac.case_data_staging USING gin (full_text public.gin_trgm_ops);


--
-- Name: case_data_staging_title_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX case_data_staging_title_idx ON almanac.case_data_staging USING gin (title public.gin_trgm_ops);


--
-- Name: idx_cases_location_geom; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_cases_location_geom ON ONLY almanac.cases USING gist (location_geom);


--
-- Name: cases_default_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_default_location_geom_idx ON almanac.cases_default USING gist (location_geom);


--
-- Name: idx_cases_status_pubdate_desc; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_cases_status_pubdate_desc ON ONLY almanac.cases USING btree (status, publication_date DESC);


--
-- Name: cases_default_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_default_status_publication_date_idx ON almanac.cases_default USING btree (status, publication_date DESC);


--
-- Name: cases_p20250801_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20250801_location_geom_idx ON almanac.cases_p20250801 USING gist (location_geom);


--
-- Name: cases_p20250801_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20250801_status_publication_date_idx ON almanac.cases_p20250801 USING btree (status, publication_date DESC);


--
-- Name: cases_p20250901_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20250901_location_geom_idx ON almanac.cases_p20250901 USING gist (location_geom);


--
-- Name: cases_p20250901_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20250901_status_publication_date_idx ON almanac.cases_p20250901 USING btree (status, publication_date DESC);


--
-- Name: cases_p20251001_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20251001_location_geom_idx ON almanac.cases_p20251001 USING gist (location_geom);


--
-- Name: cases_p20251001_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20251001_status_publication_date_idx ON almanac.cases_p20251001 USING btree (status, publication_date DESC);


--
-- Name: cases_p20251101_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20251101_lead_uuid_idx ON almanac.cases_p20251101 USING btree (lead_uuid) WHERE (lead_uuid IS NOT NULL);


--
-- Name: cases_p20251101_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20251101_location_geom_idx ON almanac.cases_p20251101 USING gist (location_geom);


--
-- Name: cases_p20251101_public_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20251101_public_uuid_idx ON almanac.cases_p20251101 USING btree (public_uuid);


--
-- Name: cases_p20251101_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20251101_status_publication_date_idx ON almanac.cases_p20251101 USING btree (status, publication_date DESC);


--
-- Name: cases_p20251101_url_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20251101_url_idx ON almanac.cases_p20251101 USING btree (url);


--
-- Name: cases_p20251201_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20251201_lead_uuid_idx ON almanac.cases_p20251201 USING btree (lead_uuid) WHERE (lead_uuid IS NOT NULL);


--
-- Name: cases_p20251201_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20251201_location_geom_idx ON almanac.cases_p20251201 USING gist (location_geom);


--
-- Name: cases_p20251201_public_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20251201_public_uuid_idx ON almanac.cases_p20251201 USING btree (public_uuid);


--
-- Name: cases_p20251201_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20251201_status_publication_date_idx ON almanac.cases_p20251201 USING btree (status, publication_date DESC);


--
-- Name: cases_p20251201_url_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20251201_url_idx ON almanac.cases_p20251201 USING btree (url);


--
-- Name: cases_p20260101_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260101_lead_uuid_idx ON almanac.cases_p20260101 USING btree (lead_uuid) WHERE (lead_uuid IS NOT NULL);


--
-- Name: cases_p20260101_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20260101_location_geom_idx ON almanac.cases_p20260101 USING gist (location_geom);


--
-- Name: cases_p20260101_public_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260101_public_uuid_idx ON almanac.cases_p20260101 USING btree (public_uuid);


--
-- Name: cases_p20260101_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20260101_status_publication_date_idx ON almanac.cases_p20260101 USING btree (status, publication_date DESC);


--
-- Name: cases_p20260101_url_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260101_url_idx ON almanac.cases_p20260101 USING btree (url);


--
-- Name: cases_p20260201_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260201_lead_uuid_idx ON almanac.cases_p20260201 USING btree (lead_uuid) WHERE (lead_uuid IS NOT NULL);


--
-- Name: cases_p20260201_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20260201_location_geom_idx ON almanac.cases_p20260201 USING gist (location_geom);


--
-- Name: cases_p20260201_public_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260201_public_uuid_idx ON almanac.cases_p20260201 USING btree (public_uuid);


--
-- Name: cases_p20260201_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20260201_status_publication_date_idx ON almanac.cases_p20260201 USING btree (status, publication_date DESC);


--
-- Name: cases_p20260201_url_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260201_url_idx ON almanac.cases_p20260201 USING btree (url);


--
-- Name: cases_p20260301_lead_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260301_lead_uuid_idx ON almanac.cases_p20260301 USING btree (lead_uuid) WHERE (lead_uuid IS NOT NULL);


--
-- Name: cases_p20260301_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20260301_location_geom_idx ON almanac.cases_p20260301 USING gist (location_geom);


--
-- Name: cases_p20260301_public_uuid_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260301_public_uuid_idx ON almanac.cases_p20260301 USING btree (public_uuid);


--
-- Name: cases_p20260301_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_p20260301_status_publication_date_idx ON almanac.cases_p20260301 USING btree (status, publication_date DESC);


--
-- Name: cases_p20260301_url_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_p20260301_url_idx ON almanac.cases_p20260301 USING btree (url);


--
-- Name: cases_template_active_pub_desc; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_template_active_pub_desc ON almanac.cases_template USING btree (publication_date DESC) WHERE (status = 'ACTIVE'::almanac.case_status);


--
-- Name: cases_template_location_geom_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_template_location_geom_idx ON almanac.cases_template USING gist (location_geom);


--
-- Name: cases_template_status_publication_date_idx; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX cases_template_status_publication_date_idx ON almanac.cases_template USING btree (status, publication_date DESC);


--
-- Name: cases_template_ux_lead_uuid; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_template_ux_lead_uuid ON almanac.cases_template USING btree (lead_uuid) WHERE (lead_uuid IS NOT NULL);


--
-- Name: cases_template_ux_public_uuid; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_template_ux_public_uuid ON almanac.cases_template USING btree (public_uuid);


--
-- Name: cases_template_ux_url; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE UNIQUE INDEX cases_template_ux_url ON almanac.cases_template USING btree (url);


--
-- Name: idx_api_usage_date; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_api_usage_date ON almanac.api_usage_log USING btree (called_at);


--
-- Name: idx_api_usage_service; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_api_usage_service ON almanac.api_usage_log USING btree (service, called_at);


--
-- Name: idx_assets_file_type; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_assets_file_type ON almanac.assets USING btree (file_type);


--
-- Name: idx_assets_metadata; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_assets_metadata ON almanac.assets USING gin (metadata);


--
-- Name: idx_assets_related_cases; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_assets_related_cases ON almanac.assets USING gin (related_cases);


--
-- Name: idx_assets_related_investigations; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_assets_related_investigations ON almanac.assets USING gin (related_investigations);


--
-- Name: idx_assets_source; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_assets_source ON almanac.assets USING btree (source_type, source_uuid);


--
-- Name: idx_cds_fts_vector; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_cds_fts_vector ON almanac.case_data_staging USING gin (fts_vector);


--
-- Name: idx_derivations_lookup; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_derivations_lookup ON almanac.search_derivations USING btree (derivation);


--
-- Name: idx_media_evidence_case_ref; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_media_evidence_case_ref ON almanac.media_evidence USING btree (case_id, case_publication_date);


--
-- Name: idx_media_evidence_evidence_type; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_media_evidence_evidence_type ON almanac.media_evidence USING btree (evidence_type);


--
-- Name: idx_media_evidence_location_geom; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_media_evidence_location_geom ON almanac.media_evidence USING gist (location_geom);


--
-- Name: idx_search_derivations_trgm; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_search_derivations_trgm ON almanac.search_derivations USING gin (derivation public.gin_trgm_ops);


--
-- Name: idx_search_synonyms_trgm; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_search_synonyms_trgm ON almanac.search_synonyms USING gin (synonym public.gin_trgm_ops);


--
-- Name: idx_search_terms_trgm; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_search_terms_trgm ON almanac.search_terms USING gin (base_term public.gin_trgm_ops);


--
-- Name: idx_synonyms_lookup; Type: INDEX; Schema: almanac; Owner: hunter_admin
--

CREATE INDEX idx_synonyms_lookup ON almanac.search_synonyms USING btree (synonym);


--
-- Name: acquisition_log_default_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_default_lead_uuid_idx;


--
-- Name: acquisition_log_default_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_default_pkey;


--
-- Name: acquisition_log_p20250801_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20250801_lead_uuid_idx;


--
-- Name: acquisition_log_p20250801_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20250801_pkey;


--
-- Name: acquisition_log_p20250901_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20250901_lead_uuid_idx;


--
-- Name: acquisition_log_p20250901_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20250901_pkey;


--
-- Name: acquisition_log_p20251001_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20251001_lead_uuid_idx;


--
-- Name: acquisition_log_p20251001_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20251001_pkey;


--
-- Name: acquisition_log_p20251101_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20251101_lead_uuid_idx;


--
-- Name: acquisition_log_p20251101_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20251101_pkey;


--
-- Name: acquisition_log_p20251201_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20251201_lead_uuid_idx;


--
-- Name: acquisition_log_p20251201_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20251201_pkey;


--
-- Name: acquisition_log_p20260101_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20260101_lead_uuid_idx;


--
-- Name: acquisition_log_p20260101_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20260101_pkey;


--
-- Name: acquisition_log_p20260201_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20260201_lead_uuid_idx;


--
-- Name: acquisition_log_p20260201_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20260201_pkey;


--
-- Name: acquisition_log_p20260301_lead_uuid_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_acq_lead_uuid ATTACH PARTITION almanac.acquisition_log_p20260301_lead_uuid_idx;


--
-- Name: acquisition_log_p20260301_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.acquisition_log_pkey ATTACH PARTITION almanac.acquisition_log_p20260301_pkey;


--
-- Name: case_content_default_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_default_pkey;


--
-- Name: case_content_default_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_default_search_vector_idx;


--
-- Name: case_content_p20250801_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20250801_pkey;


--
-- Name: case_content_p20250801_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20250801_search_vector_idx;


--
-- Name: case_content_p20250901_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20250901_pkey;


--
-- Name: case_content_p20250901_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20250901_search_vector_idx;


--
-- Name: case_content_p20251001_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20251001_pkey;


--
-- Name: case_content_p20251001_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20251001_search_vector_idx;


--
-- Name: case_content_p20251101_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20251101_pkey;


--
-- Name: case_content_p20251101_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20251101_search_vector_idx;


--
-- Name: case_content_p20251201_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20251201_pkey;


--
-- Name: case_content_p20251201_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20251201_search_vector_idx;


--
-- Name: case_content_p20260101_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20260101_pkey;


--
-- Name: case_content_p20260101_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20260101_search_vector_idx;


--
-- Name: case_content_p20260201_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20260201_pkey;


--
-- Name: case_content_p20260201_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20260201_search_vector_idx;


--
-- Name: case_content_p20260301_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.case_content_pkey ATTACH PARTITION almanac.case_content_p20260301_pkey;


--
-- Name: case_content_p20260301_search_vector_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_case_content_tsv ATTACH PARTITION almanac.case_content_p20260301_search_vector_idx;


--
-- Name: cases_default_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_default_location_geom_idx;


--
-- Name: cases_default_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_default_pkey;


--
-- Name: cases_default_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_default_status_publication_date_idx;


--
-- Name: cases_default_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_default_url_publication_date_key;


--
-- Name: cases_p20250801_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20250801_location_geom_idx;


--
-- Name: cases_p20250801_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20250801_pkey;


--
-- Name: cases_p20250801_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20250801_status_publication_date_idx;


--
-- Name: cases_p20250801_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20250801_url_publication_date_key;


--
-- Name: cases_p20250901_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20250901_location_geom_idx;


--
-- Name: cases_p20250901_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20250901_pkey;


--
-- Name: cases_p20250901_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20250901_status_publication_date_idx;


--
-- Name: cases_p20250901_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20250901_url_publication_date_key;


--
-- Name: cases_p20251001_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20251001_location_geom_idx;


--
-- Name: cases_p20251001_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20251001_pkey;


--
-- Name: cases_p20251001_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20251001_status_publication_date_idx;


--
-- Name: cases_p20251001_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20251001_url_publication_date_key;


--
-- Name: cases_p20251101_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20251101_location_geom_idx;


--
-- Name: cases_p20251101_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20251101_pkey;


--
-- Name: cases_p20251101_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20251101_status_publication_date_idx;


--
-- Name: cases_p20251101_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20251101_url_publication_date_key;


--
-- Name: cases_p20251201_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20251201_location_geom_idx;


--
-- Name: cases_p20251201_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20251201_pkey;


--
-- Name: cases_p20251201_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20251201_status_publication_date_idx;


--
-- Name: cases_p20251201_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20251201_url_publication_date_key;


--
-- Name: cases_p20260101_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20260101_location_geom_idx;


--
-- Name: cases_p20260101_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20260101_pkey;


--
-- Name: cases_p20260101_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20260101_status_publication_date_idx;


--
-- Name: cases_p20260101_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20260101_url_publication_date_key;


--
-- Name: cases_p20260201_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20260201_location_geom_idx;


--
-- Name: cases_p20260201_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20260201_pkey;


--
-- Name: cases_p20260201_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20260201_status_publication_date_idx;


--
-- Name: cases_p20260201_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20260201_url_publication_date_key;


--
-- Name: cases_p20260301_location_geom_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_location_geom ATTACH PARTITION almanac.cases_p20260301_location_geom_idx;


--
-- Name: cases_p20260301_pkey; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_pkey ATTACH PARTITION almanac.cases_p20260301_pkey;


--
-- Name: cases_p20260301_status_publication_date_idx; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.idx_cases_status_pubdate_desc ATTACH PARTITION almanac.cases_p20260301_status_publication_date_idx;


--
-- Name: cases_p20260301_url_publication_date_key; Type: INDEX ATTACH; Schema: almanac; Owner: hunter_admin
--

ALTER INDEX almanac.cases_url_publication_date_key ATTACH PARTITION almanac.cases_p20260301_url_publication_date_key;


--
-- Name: active_investigations _RETURN; Type: RULE; Schema: almanac; Owner: hunter_admin
--

CREATE OR REPLACE VIEW almanac.active_investigations AS
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
   FROM ((almanac.investigations i
     LEFT JOIN almanac.investigation_nodes n ON ((i.id = n.investigation_id)))
     LEFT JOIN almanac.investigation_links l ON ((i.id = l.investigation_id)))
  WHERE (i.status = 'ACTIVE'::almanac.investigation_status)
  GROUP BY i.id;


--
-- Name: case_content trg_case_content_tsv; Type: TRIGGER; Schema: almanac; Owner: hunter_admin
--

CREATE TRIGGER trg_case_content_tsv BEFORE INSERT OR UPDATE ON almanac.case_content FOR EACH ROW EXECUTE FUNCTION almanac.cases_tsvector_update();


--
-- Name: cases trg_cases_touch; Type: TRIGGER; Schema: almanac; Owner: hunter_admin
--

CREATE TRIGGER trg_cases_touch BEFORE UPDATE ON almanac.cases FOR EACH ROW EXECUTE FUNCTION almanac.touch_modified();


--
-- Name: investigations trg_investigations_touch; Type: TRIGGER; Schema: almanac; Owner: hunter_admin
--

CREATE TRIGGER trg_investigations_touch BEFORE UPDATE ON almanac.investigations FOR EACH ROW EXECUTE FUNCTION almanac.touch_modified();


--
-- Name: acquisition_router trg_router_partition_month; Type: TRIGGER; Schema: almanac; Owner: hunter_admin
--

CREATE TRIGGER trg_router_partition_month BEFORE INSERT OR UPDATE ON almanac.acquisition_router FOR EACH ROW EXECUTE FUNCTION almanac.update_router_partition_month();


--
-- Name: acquisition_log fk_acq_source; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.acquisition_log
    ADD CONSTRAINT fk_acq_source FOREIGN KEY (source_id) REFERENCES almanac.sources(id) ON DELETE SET NULL;


--
-- Name: case_data_staging fk_acquisition_router; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.case_data_staging
    ADD CONSTRAINT fk_acquisition_router FOREIGN KEY (uuid) REFERENCES almanac.acquisition_router(lead_uuid) ON DELETE CASCADE;


--
-- Name: case_content fk_case_content_case; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.case_content
    ADD CONSTRAINT fk_case_content_case FOREIGN KEY (case_id, publication_date) REFERENCES almanac.cases(id, publication_date) ON DELETE CASCADE;


--
-- Name: cases fk_cases_lead_uuid; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.cases
    ADD CONSTRAINT fk_cases_lead_uuid FOREIGN KEY (lead_uuid) REFERENCES almanac.acquisition_router(lead_uuid) ON DELETE SET NULL;


--
-- Name: cases fk_cases_source; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE almanac.cases
    ADD CONSTRAINT fk_cases_source FOREIGN KEY (source_id) REFERENCES almanac.sources(id) ON DELETE SET NULL;


--
-- Name: investigation_links fk_link_investigation; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_links
    ADD CONSTRAINT fk_link_investigation FOREIGN KEY (investigation_id) REFERENCES almanac.investigations(id) ON DELETE CASCADE;


--
-- Name: investigation_links fk_link_node_a; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_links
    ADD CONSTRAINT fk_link_node_a FOREIGN KEY (node_a_id) REFERENCES almanac.investigation_nodes(id) ON DELETE CASCADE;


--
-- Name: investigation_links fk_link_node_b; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_links
    ADD CONSTRAINT fk_link_node_b FOREIGN KEY (node_b_id) REFERENCES almanac.investigation_nodes(id) ON DELETE CASCADE;


--
-- Name: media_evidence fk_media_evidence_case; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.media_evidence
    ADD CONSTRAINT fk_media_evidence_case FOREIGN KEY (case_id, case_publication_date) REFERENCES almanac.cases(id, publication_date) ON DELETE CASCADE;


--
-- Name: investigation_nodes fk_node_investigation; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.investigation_nodes
    ADD CONSTRAINT fk_node_investigation FOREIGN KEY (investigation_id) REFERENCES almanac.investigations(id) ON DELETE CASCADE;


--
-- Name: processed_file_outputs fk_output_to_parent_log; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.processed_file_outputs
    ADD CONSTRAINT fk_output_to_parent_log FOREIGN KEY (parent_file_hash) REFERENCES almanac.processed_files_log(file_hash) ON DELETE CASCADE;


--
-- Name: acquisition_router fk_router_source; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.acquisition_router
    ADD CONSTRAINT fk_router_source FOREIGN KEY (source_id) REFERENCES almanac.sources(id) ON DELETE SET NULL;


--
-- Name: sources fk_sources_domain; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.sources
    ADD CONSTRAINT fk_sources_domain FOREIGN KEY (domain_id) REFERENCES almanac.source_domains(id) ON DELETE SET NULL;


--
-- Name: search_derivations search_derivations_base_term_fkey; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.search_derivations
    ADD CONSTRAINT search_derivations_base_term_fkey FOREIGN KEY (base_term) REFERENCES almanac.search_terms(base_term) ON DELETE CASCADE;


--
-- Name: search_synonyms search_synonyms_base_term_fkey; Type: FK CONSTRAINT; Schema: almanac; Owner: hunter_admin
--

ALTER TABLE ONLY almanac.search_synonyms
    ADD CONSTRAINT search_synonyms_base_term_fkey FOREIGN KEY (base_term) REFERENCES almanac.search_terms(base_term) ON DELETE CASCADE;


--
-- Name: SCHEMA almanac; Type: ACL; Schema: -; Owner: hunter_admin
--

GRANT USAGE ON SCHEMA almanac TO hunter_app_user;


--
-- Name: FUNCTION cases_tsvector_update(); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.cases_tsvector_update() TO hunter_app_user;


--
-- Name: FUNCTION generate_case_summary(p_case_id bigint); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.generate_case_summary(p_case_id bigint) TO hunter_app_user;


--
-- Name: FUNCTION get_case_complexity(p_case_id bigint); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.get_case_complexity(p_case_id bigint) TO hunter_app_user;


--
-- Name: FUNCTION get_case_statistics(); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.get_case_statistics() TO hunter_app_user;


--
-- Name: FUNCTION get_nearby_cases(lat double precision, lon double precision, radius_meters double precision); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.get_nearby_cases(lat double precision, lon double precision, radius_meters double precision) TO hunter_app_user;


--
-- Name: FUNCTION perform_custom_maintenance(); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.perform_custom_maintenance() TO hunter_app_user;


--
-- Name: FUNCTION touch_modified(); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.touch_modified() TO hunter_app_user;


--
-- Name: FUNCTION update_router_partition_month(); Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT ALL ON FUNCTION almanac.update_router_partition_month() TO hunter_app_user;


--
-- Name: TABLE acquisition_log; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.acquisition_log TO hunter_app_user;


--
-- Name: TABLE acquisition_log_default; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.acquisition_log_default TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20250801; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.acquisition_log_p20250801 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20250901; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.acquisition_log_p20250901 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20251001; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.acquisition_log_p20251001 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20251101; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.acquisition_log_p20251101 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20251201; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.acquisition_log_p20251201 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20260101; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.acquisition_log_p20260101 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20260201; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.acquisition_log_p20260201 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_p20260301; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.acquisition_log_p20260301 TO hunter_app_user;


--
-- Name: TABLE acquisition_log_template; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.acquisition_log_template TO hunter_app_user;


--
-- Name: TABLE acquisition_router; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.acquisition_router TO hunter_app_user;


--
-- Name: TABLE active_investigations; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.active_investigations TO hunter_app_user;


--
-- Name: TABLE api_usage_log; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.api_usage_log TO hunter_app_user;


--
-- Name: TABLE assets; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,UPDATE ON TABLE almanac.assets TO hunter_app_user;


--
-- Name: TABLE cases; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.cases TO hunter_app_user;


--
-- Name: TABLE case_category_stats; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_category_stats TO hunter_app_user;


--
-- Name: TABLE case_content; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.case_content TO hunter_app_user;


--
-- Name: TABLE case_content_default; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.case_content_default TO hunter_app_user;


--
-- Name: TABLE case_content_p20250801; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.case_content_p20250801 TO hunter_app_user;


--
-- Name: TABLE case_content_p20250901; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.case_content_p20250901 TO hunter_app_user;


--
-- Name: TABLE case_content_p20251001; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.case_content_p20251001 TO hunter_app_user;


--
-- Name: TABLE case_content_p20251101; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_content_p20251101 TO hunter_app_user;


--
-- Name: TABLE case_content_p20251201; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_content_p20251201 TO hunter_app_user;


--
-- Name: TABLE case_content_p20260101; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_content_p20260101 TO hunter_app_user;


--
-- Name: TABLE case_content_p20260201; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_content_p20260201 TO hunter_app_user;


--
-- Name: TABLE case_content_p20260301; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_content_p20260301 TO hunter_app_user;


--
-- Name: TABLE case_content_template; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_content_template TO hunter_app_user;


--
-- Name: TABLE case_data_staging; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,UPDATE ON TABLE almanac.case_data_staging TO hunter_app_user;


--
-- Name: TABLE investigation_nodes; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.investigation_nodes TO hunter_app_user;


--
-- Name: TABLE media_evidence; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.media_evidence TO hunter_app_user;


--
-- Name: TABLE case_summaries; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.case_summaries TO hunter_app_user;


--
-- Name: TABLE cases_default; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.cases_default TO hunter_app_user;


--
-- Name: TABLE cases_p20250801; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.cases_p20250801 TO hunter_app_user;


--
-- Name: TABLE cases_p20250901; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.cases_p20250901 TO hunter_app_user;


--
-- Name: TABLE cases_p20251001; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.cases_p20251001 TO hunter_app_user;


--
-- Name: TABLE cases_p20251101; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.cases_p20251101 TO hunter_app_user;


--
-- Name: TABLE cases_p20251201; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.cases_p20251201 TO hunter_app_user;


--
-- Name: TABLE cases_p20260101; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.cases_p20260101 TO hunter_app_user;


--
-- Name: TABLE cases_p20260201; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.cases_p20260201 TO hunter_app_user;


--
-- Name: TABLE cases_p20260301; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.cases_p20260301 TO hunter_app_user;


--
-- Name: TABLE cases_template; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.cases_template TO hunter_app_user;


--
-- Name: TABLE source_domains; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.source_domains TO hunter_app_user;


--
-- Name: TABLE foreman_agents; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.foreman_agents TO hunter_app_user;


--
-- Name: TABLE investigation_links; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.investigation_links TO hunter_app_user;


--
-- Name: TABLE investigations; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.investigations TO hunter_app_user;


--
-- Name: TABLE investigation_complexity; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.investigation_complexity TO hunter_app_user;


--
-- Name: SEQUENCE investigation_links_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.investigation_links_id_seq TO hunter_app_user;


--
-- Name: SEQUENCE investigation_nodes_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.investigation_nodes_id_seq TO hunter_app_user;


--
-- Name: SEQUENCE investigations_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.investigations_id_seq TO hunter_app_user;


--
-- Name: TABLE keyword_library; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.keyword_library TO hunter_app_user;


--
-- Name: SEQUENCE media_evidence_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.media_evidence_id_seq TO hunter_app_user;


--
-- Name: TABLE model_metadata; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.model_metadata TO hunter_app_user;


--
-- Name: TABLE processed_file_outputs; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.processed_file_outputs TO hunter_app_user;


--
-- Name: SEQUENCE processed_file_outputs_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.processed_file_outputs_id_seq TO hunter_app_user;


--
-- Name: TABLE processed_files_log; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.processed_files_log TO hunter_app_user;


--
-- Name: TABLE schema_version; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.schema_version TO hunter_app_user;


--
-- Name: TABLE search_derivations; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.search_derivations TO hunter_app_user;


--
-- Name: TABLE search_synonyms; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.search_synonyms TO hunter_app_user;


--
-- Name: TABLE search_terms; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.search_terms TO hunter_app_user;


--
-- Name: SEQUENCE source_domains_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.source_domains_id_seq TO hunter_app_user;


--
-- Name: TABLE sources; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: COLUMN sources.consecutive_failures; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT UPDATE(consecutive_failures) ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: COLUMN sources.last_success_date; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT UPDATE(last_success_date) ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: COLUMN sources.last_failure_date; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT UPDATE(last_failure_date) ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: COLUMN sources.last_checked_date; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT UPDATE(last_checked_date) ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: COLUMN sources.next_release_date; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT UPDATE(next_release_date) ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: COLUMN sources.last_known_item_id; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT UPDATE(last_known_item_id) ON TABLE almanac.sources TO hunter_app_user;


--
-- Name: SEQUENCE sources_id_seq; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,USAGE ON SEQUENCE almanac.sources_id_seq TO hunter_app_user;


--
-- Name: TABLE system_tasks; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT,INSERT,DELETE,UPDATE ON TABLE almanac.system_tasks TO hunter_app_user;


--
-- Name: TABLE v_search_dictionary; Type: ACL; Schema: almanac; Owner: hunter_admin
--

GRANT SELECT ON TABLE almanac.v_search_dictionary TO hunter_app_user;


--
-- Name: DEFAULT PRIVILEGES FOR TABLES; Type: DEFAULT ACL; Schema: almanac; Owner: hunter_admin
--

ALTER DEFAULT PRIVILEGES FOR ROLE hunter_admin IN SCHEMA almanac GRANT SELECT ON TABLES TO hunter_app_user;


--
-- PostgreSQL database dump complete
--

