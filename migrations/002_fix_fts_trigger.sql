-- =======================================================
-- Hunter's Almanac: Migration 014
-- This script fixes the cases_tsvector_update trigger to
-- work with our new, normalized cases and case_content tables.
-- =======================================================

-- We must DROP the old trigger first before we can replace the function.
DROP TRIGGER IF EXISTS update_case_search_vector ON public.case_content;

-- Now, create the new, smarter function.
CREATE OR REPLACE FUNCTION public.cases_tsvector_update()
RETURNS TRIGGER AS $$
DECLARE
    case_title TEXT;
BEGIN
    -- This is the pointer lookup. We get the title from the 'cases' table.
    SELECT title INTO case_title FROM public.cases WHERE id = NEW.case_id;

    -- Now we can build the search vector with both pieces of intel.
    NEW.search_vector =
        setweight(to_tsvector('english', coalesce(case_title,'')), 'A') ||
        setweight(to_tsvector('english', coalesce(NEW.full_text,'')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Finally, re-attach the trigger to the case_content table.
CREATE TRIGGER update_case_search_vector
BEFORE INSERT OR UPDATE ON public.case_content
FOR EACH ROW EXECUTE FUNCTION public.cases_tsvector_update();

