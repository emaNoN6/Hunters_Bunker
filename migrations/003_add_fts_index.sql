-- =======================================================
-- Hunter's Almanac: Migration 003
-- This script creates the Full-Text Search (FTS) index
-- on the cases table, enabling fast and intelligent
-- searching of case titles and text.
-- =======================================================

-- First, we need to create a function that will automatically
-- update our search_vector column whenever a case is inserted or updated.
-- This is a trigger function.
CREATE OR REPLACE FUNCTION cases_tsvector_update() RETURNS TRIGGER AS $$
BEGIN
    NEW.search_vector = 
        setweight(to_tsvector('english', coalesce(NEW.title,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.full_text,'')), 'B');
    RETURN NEW;
END
$$ LANGUAGE plpgsql;

-- Next, we create the trigger itself. This tells the database to run
-- our function before any INSERT or UPDATE on the cases table.
CREATE TRIGGER tsvectorupdate BEFORE INSERT OR UPDATE
ON cases FOR EACH ROW EXECUTE FUNCTION cases_tsvector_update();

-- Finally, we create the GIN index on the pre-calculated search_vector column.
-- This is the spell that makes searching lightning fast.
CREATE INDEX cases_search_vector_idx ON cases USING GIN (search_vector);
