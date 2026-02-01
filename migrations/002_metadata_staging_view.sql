DROP VIEW IF EXISTS almanac.v_staging_expanded;
CREATE OR REPLACE VIEW almanac.v_staging_expanded AS
SELECT cds.uuid,
       cds.title,
       cds.full_text,

       -- Simple text fields
       cds.metadata ->> 'flair'                                 AS flair,
       cds.metadata ->> 'author'                                AS author,
       cds.metadata ->> 'post_id'                               AS post_id,
       cds.metadata ->> 'subreddit'                             AS subreddit,

       -- Media fields (your JSON uses media.type, not media.media_type)
       cds.metadata #>> '{media,url}'                           AS url,
       cds.metadata #>> '{media,type}'                          AS media_type,
       NULLIF(cds.metadata #>> '{media,duration}', '')::numeric AS media_duration,
       cds.metadata #>> '{media,fallback_url}'                  AS media_fallback,

       -- Numeric fields
       NULLIF(cds.metadata ->> 'score', '')::numeric            AS score,
       NULLIF(cds.metadata ->> 'num_comments', '')::int         AS num_comments,

       -- Boolean fields
       NULLIF(cds.metadata ->> 'is_self', '')::boolean          AS is_self

FROM case_data_staging cds;