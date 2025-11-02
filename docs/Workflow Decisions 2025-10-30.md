# Hunters_Bunker Workflow Design - Master Reference

**Date:** October 30, 2025
**Status:** Design finalized, ready for implementation

---

## 1. Triage Decision Categories

### CASE (C key)

**What it is:** Actual paranormal case worth investigating
**Action:**

- Promote to `cases` + `case_content` tables
- Update `acquisition_router.status = 'PROMOTED'`
- Delete from `case_data_staging`
- Calculate initial `cases.status = 'NEW'`

### NOT A CASE (N key)

**What it is:** Legitimately matched keywords but has mundane explanation

- Example: "Scratching in walls at night" → It's mice, not ghosts
  **Why keep separate from junk:** Valuable for ML training (teaches false positive patterns)
  **Action:**
- Update `acquisition_router.status = 'REVIEWED'`
- Delete from `case_data_staging`
- (Future: optionally save to training_data/not_a_case/)

### JUNK (J key) - Rename from "Skip"

**What it is:** Pure garbage with zero value

- Examples: "Tell me your spooky stories" posts, listicles, clickbait
  **Action:**
- Update `acquisition_router.status = 'IGNORED'`
- Delete from `case_data_staging`
- Never re-download

### NO DECISION (blank)

**What it is:** User hasn't decided yet
**Action:**

- Stays in staging with current status (NEW or TRIAGED)
- Subject to time decay

---

## 2. Status Lifecycles

### acquisition_router.status (Lead Lifecycle)

```
NEW       → Haven't viewed yet (shows in triage pane)
TRIAGED   → Viewed but no decision made (shows in "Take a Second Look")
PROMOTED  → Became a case (in cases table now)
REVIEWED  → Not a case (useful for training)
IGNORED   → Junk or expired (tombstone prevents re-download)
```

**Decision: Drop EXPIRED as separate status**

- IGNORED covers both manual junk and auto-expired items
- Same outcome: prevent re-download, delete from staging
- Simpler is better

### cases.status (Case Investigation Lifecycle)

```
NEW     → Just promoted from triage, ready for case tools
ACTIVE  → Under active investigation
CLOSED  → Investigation complete
```

**Note:** TRIAGED stays in enum but unused for now

---

## 3. Time Decay System

### Severity Score

**Location:** `acquisition_router.severity_score` (not in staging)
**Why router:** Single source of truth, persists after staging cleanup

**Initial Scoring (pre-ML):**

```python
# Keyword-based scoring using priority from keyword_library
HIGH priority keywords (demon, possession, UFO) → score = 100
MEDIUM priority keywords (ghost, haunted) → score = 50  
LOW priority keywords (scratches, dreams) → score = 25
```

### Decay Formula: Half-Life Exponential Decay

**Mathematical Formula:**

```
S(t) = S₀ × (0.5)^(t / t_half)

where:
  S(t)    = current score at time t
  S₀      = initial score
  t       = days elapsed since last update
  t_half  = half-life in days (score halves every t_half days)
```

**Half-Life by Priority Level:**

```
HIGH priority   (S₀ ≥ 70): t_half = 45 days → expires at ~90 days
MEDIUM priority (S₀ ≥ 40): t_half = 30 days → expires at ~60 days  
LOW priority    (S₀ < 40): t_half = 15 days → expires at ~30 days
```

**Expiration Floor:** Score expires when S(t) ≤ 0.25

**Example Timeline (HIGH priority, S₀ = 100, t_half = 45):**

```
Day   0: S = 100.0
Day  45: S =  50.0  (one half-life)
Day  90: S =  25.0  (two half-lives) → EXPIRES at 0.25 floor
Day 180: S =   6.25 (four half-lives, but already expired)
```

**Python Implementation:**

```python
def calculate_current_score(initial_score, last_update_time):
    """Calculate current score using half-life decay"""
    days_elapsed = (datetime.now(UTC) - last_update_time).total_seconds() / 86400
    
    # Determine half-life based on initial score
    if initial_score >= 70:
        half_life = 45
    elif initial_score >= 40:
        half_life = 30
    else:
        half_life = 15
    
    # Apply half-life decay formula
    current_score = initial_score * (0.5 ** (days_elapsed / half_life))
    
    # Floor at 0.25 (below this = expired)
    return max(0.25, current_score) if current_score > 0.25 else 0
```

**SQL Implementation:**

```sql
-- Decay function with half-life formula
CREATE OR REPLACE FUNCTION decay_severity_scores()
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE acquisition_router
    SET 
        severity_score = CASE
            WHEN severity_score * POW(0.5, 
                EXTRACT(EPOCH FROM (NOW() - last_score_update)) / 86400 / 
                CASE 
                    WHEN severity_score >= 70 THEN 45  -- High priority
                    WHEN severity_score >= 40 THEN 30  -- Medium priority
                    ELSE 15                             -- Low priority
                END
            ) <= 0.25 THEN 0.25  -- Floor at expiration threshold
            ELSE severity_score * POW(0.5,
                EXTRACT(EPOCH FROM (NOW() - last_score_update)) / 86400 /
                CASE 
                    WHEN severity_score >= 70 THEN 45
                    WHEN severity_score >= 40 THEN 30
                    ELSE 15
                END
            )
        END,
        last_score_update = NOW()
    WHERE status IN ('NEW', 'TRIAGED')
    AND severity_score > 0.25;
    
    -- Mark expired items
    UPDATE acquisition_router
    SET status = 'IGNORED'
    WHERE status IN ('NEW', 'TRIAGED')
    AND severity_score <= 0.25;
    
    -- Clean up staging
    DELETE FROM case_data_staging
    WHERE uuid IN (
        SELECT lead_uuid 
        FROM acquisition_router 
        WHERE status = 'IGNORED'
    );
END;
$$;
```

**Scheduling:** pg_cron + GUI startup

```sql
-- Run every 4 hours while Docker is running
SELECT cron.schedule(
    'decay-scores',
    '0 */4 * * *',
    $$SELECT decay_severity_scores();$$
);
```

**Plus:** Python calls `decay_severity_scores()` on GUI startup to catch up if laptop was off for days

### Manual Score Override

**Keyboard shortcuts in triage:**

- `1` key → Set score = 25 (low priority)
- `2` key → Set score = 50 (medium priority)
- `3` key → Set score = 100 (high priority)
- `U` key → Mark UNDECIDED (future: freezes decay)

---

## 4. Database Schema Changes

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
-- (Already has: NEW, PROMOTED, IGNORED)
-- (Dropping: EXPIRED - just use IGNORED)
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
-- Original purpose was unclear, became redundant
DROP TABLE acquisition_log CASCADE;
```

---

## 5. Item Identification System

### Composite Key: (agent_type, item_id)

**Reddit:**

```python
agent_type: 'reddit'
item_id: 'abc123'  # submission_id
content_url: NULL or external URL for link posts
# Reconstruct: f"https://reddit.com/comments/{item_id}"
```

**GNews:**

```python
agent_type: 'gnews'
item_id: '1cc1f9cfd6918671c053d59d5cf839fb'  # article_id from API
content_url: actual article URL
# Reconstruct: use content_url
```

**Manual HTML Agent (NEW):**

```python
agent_type: 'manual'
item_id: 'https://coolsite.com/paranormal-story'  # Full URL
content_url: NULL
# Reconstruct: use item_id directly
```

**Deduplication:**

```python
def is_duplicate(agent_type, item_id):
    return exists("SELECT 1 FROM acquisition_router 
                   WHERE agent_type=%s AND item_id=%s")
```

---

## 6. Manual HTML Agent

### Purpose

Allow user to manually add URLs they find interesting

- Use case: Browser tabs with articles to review later
- Bulk import: Paste multiple URLs at once

### GUI Addition

```python
# Add button to triage desk
"Add URL Manually" button
  ↓
Dialog: Enter URL or paste multiple (one per line)
  ↓
Manual agent fetches content
  ↓
Scores via keywords
  ↓
Appears in triage pane immediately
```

### Database Setup

```python
# In db_seeder.py
domains_to_add.append({
    'domain_name': 'manual',
    'agent_type': 'manual',
    'max_concurrent_requests': 1
})

sources_to_add.append({
    'source_name': 'Manual Additions',
    'domain_name': 'manual',
    'target': 'user_provided',
    'purpose': 'lead_generation'
})
```

---

## 7. Transaction Safety

### All Filing Operations Wrapped

```python
def file_as_case(lead_uuid):
    conn.autocommit = False
    try:
        # 1. Get staging data
        # 2. Get router data  
        # 3. INSERT into cases
        # 4. INSERT into case_content
        # 5. UPDATE router status
        # 6. DELETE from staging
        conn.commit()
    except:
        conn.rollback()
        # Item stays in router + staging
        # Fix manually in DataGrip if needed
```

**Applies to:**

- `file_as_case()` (6 operations)
- `file_as_not_case()` (2 operations)
- `file_as_junk()` (2 operations)

---

## 8. GUI Updates Needed

### Triage Pane

**Two views:**

1. **Default: "NEW" items** - Unviewed leads, sorted by severity_score DESC
2. **"Take a Second Look"** - TRIAGED items (viewed but no decision)

**Search bar:**

```python
# Simple text entry at top
[Search: ___________]
# Uses trgm indexes on title + full_text
# Fuzzy matching, no dropdown complexity
```

**Keyboard shortcuts:**

```
C - Mark as Case
N - Mark as Not a Case  
J - Mark as Junk (renamed from Skip)
1 - Set score to 25
2 - Set score to 50
3 - Set score to 100
U - Mark as Undecided (future)
Space/Backspace - Clear decision
```

**On item click:**

```python
def display_lead_detail(lead_data):
# Show content in detail pane
# UPDATE router: status='NEW' → 'TRIAGED' (mark as viewed)
```

### Treeview Columns

```
Title | Source | Date | Original Score | Current Score | Days Old | Decision
```

**Color coding by current_score:**

- Green (70+) = High priority
- Yellow (30-69) = Medium priority
- Red (<30) = Low priority / expiring soon
- Gray (0) = Expired

---

## 9. Implementation Priority

### Phase 1: Core Workflow (Do First)

1. Schema migrations (add columns, drop acquisition_log, update enums)
2. Implement `mark_as_triaged()` (auto-mark on view)
3. Implement filing functions with transactions:
    - `file_as_case()`
    - `file_as_not_case()`
    - `file_as_junk()`
4. Update `confirm_triage_action()` to call correct functions
5. Implement severity_score decay function + pg_cron schedule

### Phase 2: GUI Enhancements

1. Add search bar to triage pane
2. Add "Take a Second Look" button (show TRIAGED items)
3. Add keyboard shortcuts (1/2/3 for score override)
4. Add score columns to treeview
5. Implement color coding by score

### Phase 3: New Features

1. Manual HTML agent implementation
2. "Add URL Manually" button + dialog
3. Bulk URL import feature

### Phase 4: Future Enhancements

- UNDECIDED status (freeze decay)
- ML-based initial scoring (replaces keyword scoring)
- Case investigation workflow (ACTIVE/CLOSED statuses)
- Training data export for "Not a Case" items

---

## 10. Testing Checklist

### Workflow Tests

- [ ] Download new lead → appears with status='NEW'
- [ ] Click lead → status changes to 'TRIAGED'
- [ ] Mark as Case → promotes to cases table, deletes from staging
- [ ] Mark as Not Case → status='REVIEWED', deletes from staging
- [ ] Mark as Junk → status='IGNORED', deletes from staging
- [ ] No decision → stays in staging, score decays over time
- [ ] Score hits 0 → auto-marked IGNORED, deleted from staging
- [ ] Re-run scraper → skips all items in router (any status)

### Transaction Tests

- [ ] Filing fails mid-operation → rollback successful, data in router+staging
- [ ] Manual DataGrip fix → can retry filing

### Search Tests

- [ ] Search "demon" → shows matching items instantly
- [ ] Search "posession" → fuzzy matches "possession" (trgm)
- [ ] Clear search → shows all items again
- [ ] Search with filters → combines correctly

### Manual Agent Tests

- [ ] Add single URL → fetches content, scores, appears in triage
- [ ] Add bulk URLs → all process correctly
- [ ] Duplicate manual URL → skipped correctly

---

## 11. Open Questions / Future Decisions

### To Revisit Later

1. **Training data export:** When ready for ML, decide format and storage
2. **UNDECIDED implementation:** How to UI/UX for freezing decay?
3. **Case investigation workflow:** Design when building case viewer
4. **Scraper logging:** What analytics do we actually need?
5. **Router cleanup:** Archive old tombstones (>1 year)? Or keep forever?

### Known Gaps

- Case viewer/browser tool (not designed yet)
- Investigation workflow (ACTIVE/CLOSED transitions)
- Media evidence handling (exists in schema, no workflow yet)
- Geographic analysis tools (location_geom exists, unused)

---

## Appendix: Key SQL Queries

### Get Triage Items (NEW)

```sql
SELECT cds.*, ar.severity_score, ar.status,
       CASE
           WHEN ar.severity_score * POW(0.5,
               EXTRACT(EPOCH FROM (NOW() - ar.last_score_update)) / 86400 /
               CASE 
                   WHEN ar.severity_score >= 70 THEN 45
                   WHEN ar.severity_score >= 40 THEN 30
                   ELSE 15
               END
           ) <= 0.25 THEN 0.25
           ELSE ar.severity_score * POW(0.5,
               EXTRACT(EPOCH FROM (NOW() - ar.last_score_update)) / 86400 /
               CASE 
                   WHEN ar.severity_score >= 70 THEN 45
                   WHEN ar.severity_score >= 40 THEN 30
                   ELSE 15
               END
           )
       END as current_score
FROM case_data_staging cds
JOIN acquisition_router ar ON cds.uuid = ar.lead_uuid
WHERE ar.status = 'NEW'
ORDER BY current_score DESC;
```

### Get Second Look Items (TRIAGED)

```sql
SELECT cds.*, ar.severity_score, ar.status, ar.last_score_update
FROM case_data_staging cds
JOIN acquisition_router ar ON cds.uuid = ar.lead_uuid
WHERE ar.status = 'TRIAGED'
ORDER BY ar.last_score_update ASC;  -- Oldest first
```

### Search Staging

```sql
SELECT cds.*, ar.severity_score
FROM case_data_staging cds
JOIN acquisition_router ar ON cds.uuid = ar.lead_uuid
WHERE ar.status IN ('NEW', 'TRIAGED')
  AND (cds.title ILIKE %s OR cds.full_text ILIKE %s)
ORDER BY ar.severity_score DESC;
```

### Check for Duplicate

```sql
SELECT 1 FROM acquisition_router
WHERE agent_type = %s AND item_id = %s;
```

### Decay Scores

```sql
-- Apply half-life decay to all active items
UPDATE acquisition_router
SET severity_score = CASE
        WHEN severity_score * POW(0.5, 
            EXTRACT(EPOCH FROM (NOW() - last_score_update)) / 86400 / 
            CASE 
                WHEN severity_score >= 70 THEN 45
                WHEN severity_score >= 40 THEN 30
                ELSE 15
            END
        ) <= 0.25 THEN 0.25
        ELSE severity_score * POW(0.5,
            EXTRACT(EPOCH FROM (NOW() - last_score_update)) / 86400 /
            CASE 
                WHEN severity_score >= 70 THEN 45
                WHEN severity_score >= 40 THEN 30
                ELSE 15
            END
        )
    END,
    last_score_update = NOW()
WHERE status IN ('NEW', 'TRIAGED')
  AND severity_score > 0.25;
```

### Auto-Expire

```sql
-- Mark items that hit the expiration floor (0.25)
UPDATE acquisition_router
SET status = 'IGNORED'
WHERE status IN ('NEW', 'TRIAGED')
  AND severity_score <= 0.25;

-- Clean up staging for expired items
DELETE FROM case_data_staging
WHERE uuid IN (
    SELECT lead_uuid FROM acquisition_router 
    WHERE status = 'IGNORED'
);
```

---

**End of Design Document**

All 7 critique points addressed ✓
All workflow questions answered ✓
Ready for implementation ✓
