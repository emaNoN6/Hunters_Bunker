CREATE VIEW almanac.v_staging_expanded AS
SELECT cds.uuid,
       cds.title,
       cds.full_text,
       cds.metadata ->> 'flair'                         AS flair,
       cds.metadata #>> '{media,url}'                   AS media_url,
       cds.metadata #>> '{media,type}'                  AS media_type,
       (cds.metadata -> 'media' -> 'duration')::numeric AS media_duration,
       cds.metadata #>> '{media,fallback_url}'          AS media_fallback,
       (cds.metadata -> 'score')::numeric               AS score,
       cds.metadata ->> 'author'                        AS author,
       (cds.metadata -> 'is_self')::boolean             AS is_self,
       cds.metadata ->> 'post_id'                       AS post_id,
       cds.metadata ->> 'subreddit'                     AS subreddit,
       (cds.metadata -> 'num_comments')::int            AS num_comments
FROM case_data_staging cds;