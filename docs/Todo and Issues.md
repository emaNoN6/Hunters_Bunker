# Hunters_Bunker TODO & Issues Tracker

**Last Updated:** October 30, 2025

A running list of things we've discussed, issues identified, and ideas to explore.

---

## ✅ Recently Resolved

### Metadata Saving

**Status:** Working!

- Added more fields to GNews dataclass
- Metadata now saving to JSONB column properly
- May tweak which fields are used, but core functionality works

### Source Name Pipeline Issue

**Status:** FIXED! ✅

- Root cause: Foremen using `source_config.get('name')` instead of `source_config.get('source_name')`
- Fixed by changing to SourceConfig dataclass with proper attribute names
- Source names now flow correctly through entire pipeline (Reddit Paranormal stays Reddit Paranormal)
- `file_new_lead()` working correctly with proper data

### GUI Performance / Framework Choice

**Status:** Resolved - staying with CustomTkinter

- Treeview performance is acceptable for current needs
- CustomTkinter works well enough for testing/development
- GUI is in "good enough to test with" state
- Minor tweaks needed but core is solid

---

## 🔥 Immediate Fixes (Do Soon)

### Code Cleanup Needed

**Problem:** Old/unused functions lying around causing confusion

- Dead code from mid-refactor states
- Functions that were replaced but not removed
- Need to audit and clean up to avoid calling wrong functions

**Examples to investigate:**

- Old foreman fallback code that's no longer needed
- Unused helper functions in db_manager
- Any other refactor artifacts

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

### Agent/Foreman Architecture Refactor

**Status:** After db_manager rewrite
**Problem:** Currently spawning one foreman instance per target (per subreddit, per search term)

- Dispatcher creates thread for "Reddit Paranormal" → reddit_foreman
- Dispatcher creates thread for "Reddit Ghosts" → reddit_foreman again
- Each foreman only handles one target

**Better Design:**

- ONE foreman per agent type (not per target)
- Foreman coordinates multiple targets internally
- Rate limiting and credentials managed at platform level
- Cleaner: Dispatcher → Agent Type → Foreman → Multiple Targets

**Why it makes sense:**

- Rate limits are per-platform (Reddit API), not per-subreddit
- Authentication is per-platform
- Aligns with domain/target schema redesign
- Foreman's actual job is to coordinate all targets for that agent

**Implementation:**

- Dispatcher spawns ONE thread for "reddit" agent
- Reddit foreman internally manages [paranormal, ghosts, humanoid, etc.]
- Same pattern for gnews, manual, etc.

### PRAW Rate Limiting / API Info

**Status:** Not implemented - AFTER foreman refactor
**Why wait:** Rate limiting makes more sense with one foreman managing all Reddit requests
**Current issue:** Reddit agent gets rate limit info from PRAW but doesn't use it
**TODO when implementing:**

- Track API usage across all subreddits
- Respect rate limits at platform level
- Log when approaching limits
- Coordinate requests across multiple targets
  **Note:** Much easier to implement when there's a single coordination point (one foreman) instead of multiple
  independent instances competing for the same rate limit

### Rate-Limited News Aggregator Strategy

**Status:** Design phase - AFTER db_manager refactor
**Priority:** Medium (affects efficient use of free tiers)

**Problem Context:**
GNews.io free tier constraints:

- 100 queries/day limit
- 10 results per query (no pagination)
- Same query returns same 10 results until news changes
- 12-hour delay (doesn't matter for paranormal cases)
- 30-day history backfill (good for new terms)

**Strategic Approach:**
Goal: Use all 100 queries/day efficiently, maximize unique article coverage

**Key Principles:**

1. **Diverse search terms** - 100 different queries, not same term 100x
2. **Morphological expansion** - Use WordsAPI cache to auto-expand base concepts
    - "mutilate" → "mutilation OR mutilate OR mutilated OR mutilating OR mutilator"
3. **Track last queried** - Don't re-query same term too soon (daily? weekly?)
4. **Adaptive prioritization** - Promote terms with good signal, pause noisy ones
5. **Auto-backfill** - New terms get 30-day history on first query

**Database Additions Needed:**

```sql
-- Track query usage and results quality
ALTER TABLE source_targets ADD COLUMN last_queried_at TIMESTAMP;
ALTER TABLE source_targets ADD COLUMN queries_today INTEGER DEFAULT 0;
ALTER TABLE source_targets ADD COLUMN quota_reset_time TIMESTAMP;
ALTER TABLE source_targets ADD COLUMN consecutive_empty_results INTEGER DEFAULT 0;
ALTER TABLE source_targets ADD COLUMN total_cases_found INTEGER DEFAULT 0;
```

**Term Management:**

- Curate ~50-100 base concepts in MEDIA_SEARCH_TERMS.md
- Auto-expand using morphology database at query time
- Track signal-to-noise ratio over time
- Eventually use local LLM to classify results (manual triage for now)

**Rotation Logic (rough allocation):**

- HIGH priority: Terms with proven results (query more often)
- MEDIUM: Decent signal (query regularly)
- LOW: Experimental/testing (rotate through)
- PAUSED: Consistently noisy (don't waste quota)

**Related Files:**

- MEDIA_SEARCH_TERMS.md - curated base terms and results tracking
- [Future] MEDIA_SEARCH_STRATEGY.md - detailed scheduling algorithm

**Note:** Design this properly before implementing. Half-done rate limiting is worse than none.

### Dataclass Migration

**Status:** In progress, agent by agent

- ✅ Reddit: Mostly done (metadata saving working)
- ✅ GNews: Done (added more fields)
- ✅ SourceConfig: Implemented and working
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

### Type Checking with mypy

**Status:** Discussed but not implemented
**Purpose:** Static type checking to catch bugs before runtime
**Why:** With dataclasses and type hints, mypy acts like a compiler

- Catches typos in attribute names (e.g., `config.name` vs `config.source_name`)
- Validates function signatures
- Prevents None/null errors
  **Setup:**

```bash
pip install mypy
mypy your_code.py
```

**Benefits with dataclasses:** Would have caught the 'name' vs 'source_name' bug immediately

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

### Manual HTML Agent

**Status:** Designed in workflow doc, not implemented
**Purpose:** User can paste URLs they find interesting
**Features:**

- Single URL or bulk paste (one per line)
- Fetches content, scores via keywords
- Appears in triage immediately
  **Priority:** Phase 3 (after core workflow working)

### Git Commit Note Hook

**Status:** Idea discussed
**Purpose:** Automatically extract inline notes from code into commit messages
**Implementation:** Git prepare-commit-msg hook that finds ` comments
**Example:**

```python
status = 'NEW'  # Changed from 'new' Fixed enum case
```

**Result in commit message:**

```
Fix source name pipeline

## Inline Notes:
- Fixed enum case
```

**Benefit:** Document small changes as you make them, not later when you forget

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
- Metadata saving works, might refine field selection later
- GUI functional for testing, minor polish needed eventually

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