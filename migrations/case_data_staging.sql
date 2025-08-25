SET SEARCH_PATH TO almanac,public;
CREATE TABLE IF NOT EXISTS case_data_staging (
  id BIGSERIAL PRIMARY KEY,                       -- surrogate key for fast internal use
  uuid UUID NOT NULL UNIQUE,                      -- foreign key and unique global identifier
  title TEXT NOT NULL,                            -- item title
  full_text TEXT NOT NULL,                        -- raw text content
  full_html TEXT,                                 -- raw HTML content, optional if available
  CONSTRAINT fk_acquisition_router FOREIGN KEY (uuid)
    REFERENCES acquisition_router(lead_uuid) ON DELETE CASCADE
);
COMMENT ON TABLE case_data_staging IS 'Holding table for freshly acquired case data';
ALTER TABLE case_data_staging OWNER TO Hunter_Admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE case_data_staging TO hunter_app_user;

/*
SELECT
  cds.id,
  cds.title,
  ar.lead_uuid,
  s.source_name,
  ar.last_seen_at
FROM case_data_staging cds
  JOIN acquisition_router ar
    ON cds.uuid = ar.lead_uuid
  JOIN sources s
    ON ar.source_id = s.id
ORDER BY ar.last_seen_at DESC;
*/