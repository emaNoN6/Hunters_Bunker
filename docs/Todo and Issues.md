# Hunters_Bunker TODO & Issues Tracker
**Last Updated:** October 30, 2025

A running list of things we've discussed, issues identified, and ideas to explore.

---

## 🔥 Immediate Fixes (Do Soon)

### Source Name Pipeline Issue
**Problem:** Source name getting truncated somewhere in the pipeline
- Getting "Reddit" instead of "Reddit Paranormal"
- Currently hacked around by passing full name back
- Need to trace through the call chain and find where it's getting lost
- Likely a split/parse issue or wrong field from JOIN

### Metadata Saving
**Status:** In progress
- Added more fields to GNews dataclass
- Need to wire up metadata saving to database properly
- JSONB column exists, just needs to be populated

---

## 🧠 Needs Thinking / Design Work

### Schema Rethink: sources vs source_domains
**Problem:** Current structure doesn't scale well
- One domain (reddit) → many subreddits = bloated sources table
- One domain (gnews_io) → many search terms = even worse bloat
- Hard to query "what did gnews give me?" without ILIKE wildcards

**Current Pain Points:**
```sql
-- This sucks:
WHERE s.source_name ILIKE 'gnews%'
```

**Possible Solution:**
Separate domain-level config from individual targets:
```
source_domains: 
  - id, domain_name (reddit, gnews_io)
  - api_key, rate_limit, health_check stuff
  
source_targets:
  - id, domain_id, target_name (paranormal, "demon search")
  - last_checked, consecutive_failures
  
acquisition_router:
  - source_domain_id, source_target_id
  - OR just use agent_type + item_id from workflow doc
```

**Questions to Answer:**
- Do we need source_id in router at all if we have agent_type?
- How do we track per-target stats (failures, last_checked)?
- Storage: 2 ints vs strings for agent_type?
- Can we still do fast queries?

---

## 📋 Major Refactoring Tasks

### db_manager Rewrite
**Status:** Next day off project
**Why:** Current code is pre-workflow-document archaeological layers
- Found old `file_new_lead()` that doesn't match new design
- Uses `item_url` instead of `(agent_type, item_id)`
- Wrong enum values, wrong conflict handling
- General spaghetti from mid-refactor state

**Needs to Implement:**
- Composite key `(agent_type, item_id)` deduplication
- Transaction-wrapped filing functions from workflow doc
- Proper status transitions (NEW → TRIAGED → PROMOTED/REVIEWED/IGNORED)
- Severity scoring and decay functions
- Clean separation of concerns

### Dataclass Migration
**Status:** In progress, agent by agent
- ✅ Reddit: Mostly done (no metadata saved yet)
- 🔨 GNews: In progress (added more fields today)
- ❓ Other agents: TBD

---

## 🔐 Security / Configuration

### Environment Variables (.env)
**Status:** Discussed but not implemented
**Why:** Security concern about API keys in config.ini
- Especially worried about billing if keys get committed to GitHub
- Want to move to .env files or PyCharm run configurations

### Git-secrets / Gitleaks
**Status:** Discussed but not implemented  
**Purpose:** Prevent accidentally committing API keys
**Options:**
- git-secrets: Pre-commit hook that blocks secrets
- gitleaks: Similar tool, different implementation
**Note:** Need to set this up before implementing .env

---

## 🎯 Schema Migrations Needed (From Workflow Doc)

These are from WORKFLOW_DECISIONS_2025-10-30.md but not yet implemented:

### acquisition_router Updates
```sql
-- Add severity scoring
ALTER TABLE acquisition_router
ADD COLUMN severity_score NUMERIC(5,2) DEFAULT 50.0,
ADD COLUMN last_score_update TIMESTAMP DEFAULT NOW();

-- Add item identification (drop item_url, use composite key)
ALTER TABLE acquisition_router
DROP COLUMN item_url,
ADD COLUMN agent_type TEXT NOT NULL,
ADD COLUMN item_id TEXT NOT NULL,
ADD COLUMN content_url TEXT,
ADD CONSTRAINT unique_agent_item UNIQUE(agent_type, item_id);

-- Update status enum
ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'REVIEWED';
ALTER TYPE lead_status ADD VALUE IF NOT EXISTS 'TRIAGED';
```

### case_data_staging Updates
```sql
-- Add search indexes
CREATE INDEX idx_staging_title_trgm ON case_data_staging 
USING gin (title gin_trgm_ops);

CREATE INDEX idx_staging_text_trgm ON case_data_staging 
USING gin (full_text gin_trgm_ops);
```

### keyword_library Updates
```sql
-- Add priority for initial scoring
ALTER TABLE keyword_library
ADD COLUMN priority TEXT DEFAULT 'MEDIUM' 
CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW'));
```

### Drop acquisition_log
```sql
-- No longer needed - router handles deduplication
DROP TABLE acquisition_log CASCADE;
```

---

## 💡 Ideas / "What If" Explorations

### Type Safety with Pydantic
**Discussion:** Use Pydantic instead of plain dataclasses
**Why:** Better validation, JSON serialization, type coercion
**Status:** Mentioned during dataclass refactor discussion
**Decision:** Not urgent, dataclasses are fine for now

### GUI Framework Alternatives
**Discussion:** Consider alternatives to CustomTkinter
**Why:** Performance issues with 600+ item treeview
**Options Discussed:**
- Qt (user had bad experience years ago)
- Web-based (user strongly prefers desktop apps)
- Stick with CustomTkinter but optimize
**Status:** Tabled for now, focusing on ListView/TreeView optimization first

### Manual HTML Agent
**Status:** Designed in workflow doc, not implemented
**Purpose:** User can paste URLs they find interesting
**Features:**
- Single URL or bulk paste (one per line)
- Fetches content, scores via keywords
- Appears in triage immediately
**Priority:** Phase 3 (after core workflow working)

---

## 🧪 Testing Needs

From WORKFLOW_DECISIONS_2025-10-30.md - these aren't tested yet:

### Workflow Tests
- [ ] Download new lead → appears with status='NEW'
- [ ] Click lead → status changes to 'TRIAGED'
- [ ] Mark as Case → promotes to cases table, deletes from staging
- [ ] Mark as Not Case → status='REVIEWED', deletes from staging
- [ ] Mark as Junk → status='IGNORED', deletes from staging
- [ ] No decision → stays in staging, score decays over time
- [ ] Score hits 0.25 → auto-marked IGNORED, deleted from staging
- [ ] Re-run scraper → skips all items in router (any status)

### Transaction Tests
- [ ] Filing fails mid-operation → rollback successful, data in router+staging
- [ ] Manual DataGrip fix → can retry filing

### Search Tests
- [ ] Search "demon" → shows matching items instantly
- [ ] Search "posession" → fuzzy matches "possession" (trgm)
- [ ] Clear search → shows all items again

---

## 📝 Notes & Observations

### Things That "Kinda Work" But Are Hacky
- Source name getting full name passed back as workaround
- db_manager cobbled together to function but needs rewrite
- Dispatcher working but could be cleaner

### Archaeological Code Layers Found
- Old `file_new_lead()` function from early dataclass refactor
- Pre-workflow-document design patterns still lingering
- Mid-refactor spaghetti that needs untangling

---

## 🎓 Lessons Learned

**From today's session:**
- Refactoring mid-stream creates archaeological layers
- "Kinda works" is a good state to iterate from
- Source/domain structure needs thought before scaling
- Having a workflow document prevents reimplementing wrong things

---

**Remember:** This is a living document. Add to it whenever we discuss something that's not immediately implemented!