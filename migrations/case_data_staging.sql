CREATE TABLE almanac.case_data_staging (
  id BIGSERIAL PRIMARY KEY,                        -- surrogate key for fast internal use
  acquisition_log_uuid UUID NOT NULL UNIQUE,       -- foreign key and unique global identifier
  full_text TEXT NOT NULL,                          -- raw text content
  full_html TEXT,                                  -- raw HTML content, optional if available
  CONSTRAINT fk_acquisition_log FOREIGN KEY (acquisition_log_uuid) REFERENCES almanac.acquisition_log(uuid) ON DELETE CASCADE
);
COMMENT ON TABLE case_data_staging IS 'Holding table for freshly acquired case data';


SELECT cd.id, cd.acquisition_log_uuid AS log_id, s.source_name,al.seen
FROM almanac.case_data_staging cd
JOIN acquisition_logal ON al.lead_uuid = cd.acquisition_log_uuid
JOIN almanac.source_domains sd ON cd.id = sd.id
JOIN almanac.sources s ON sd.id = s.domain_id