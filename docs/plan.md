# Hunters_Bunker — Improvement Plan (Derived)

Date: 2025-08-20 16:50 (local)

Note about source materials and assumptions
- The file docs/requirements.md is not present in the repository. This plan is therefore derived from:
  - docs/tasks.md (priority-ordered checklist of improvements)
  - .junie/guidelines.md (Hunter's Command Console — Development Guidelines)
  - Repository structure and module naming
- Assumptions are noted per section where requirements would normally disambiguate choices.

Goals (inferred)
- Correctness and reliability first; then architecture, quality, performance, UX, and documentation (as per docs/tasks.md ordering).
- Windows-first (PowerShell), Python 3.11.x, PostgreSQL-backed persistence with migrations.
- Keep GUI responsive with safe background work and clear user feedback.
- Improve maintainability, type safety, and observability while minimizing breaking changes.

Global constraints (inferred)
- OS/Runtime: Windows; Python 3.10–3.12 acceptable; target 3.11.x.
- DB: PostgreSQL on 127.0.0.1:5432; schema search_path = almanac,public; admin/app roles.
- Config: config.ini at repo root; currently eagerly loaded by config_manager on import; tests should avoid fatal exits.
- Tests: Standard unittest runner; prefer hermetic tests; patch DB and config behaviors.
- Heavy deps (torch/whisper) are optional; avoid requiring them for tests.

---

## 1) Core correctness and API alignment

Problems observed (from docs/tasks.md)
- Dispatcher/DB API mismatches between actions_news_search.py and hunter/db_manager.py (e.g., check_acquisition_log vs. check_acquisition_router; update_source_check_time vs. update_source_state).
- Inconsistent agent hunt() return types (tuple vs. list) cause fragile calling code.

Proposed changes
- Establish a canonical agent result type: tuple (leads: list[Lead], new_bookmark_id: str|None, status: str|None) where status is optional and defaults to None. Keep it backward compatible by accepting 2-tuple during migration window.
- Rename and align DB API and dispatcher calls:
  - check_acquisition_router(...) as the single canonical read path; deprecate check_acquisition_log alias or wrap it.
  - update_source_state(source_id, last_checked_utc: datetime, last_known_item_id: str|None, status: SourceStatus, error: str|None)
- Update actions_news_search.search_all_sources to:
  - Normalize agent result to canonical tuple.
  - Propagate success/failure and bookmarks to db_manager.update_source_state.

Rationale
- Eliminates runtime errors due to name mismatches; enforces a stable contract across agents and dispatcher.

Risks/Assumptions
- Some agents may return additional metadata; keep a dict “extras” if needed in later phases. For now, prefer minimal standardization.

Success criteria
- End-to-end hunt runs without AttributeError/KeyError; DB state reflects last check and bookmark consistently.

Phase
- Short-term (Phase 1).

---

## 2) Data model, deduplication, and URL normalization

Problems
- Duplicate checks are inconsistent and sometimes URL-only.
- Lack of centralized dedup logic; scattered checks across modules.

Proposed changes
- Introduce domain-level canonicalization:
  - URL normalization: lowercasing host, removing UTM/query trackers, normalizing scheme, removing fragments.
  - Compute normalized_url_hash (e.g., SHA-256) and store alongside raw URL.
- Single dedup service function in db_manager or a domain module:
  - is_duplicate_lead(lead: Lead) -> bool using (lead_uuid or normalized_url_hash, publication_date) per schema uniqueness.
- Database constraints and indices:
  - Ensure unique index on (normalized_url_hash, publication_date) or (url, publication_date) if hash unavailable.
  - Index lead_uuid, source_id, last_checked_date, last_known_item_id.

Rationale
- Centralized, deterministic dedup avoids re-ingestion and inconsistent triage UI.

Risks/Assumptions
- Some feeds may omit publication_date; fallback to (normalized_url_hash) uniqueness.

Success criteria
- Re-running the same hunt is idempotent; no duplicate leads appear in triage.

Phase
- Short-term for code path; DB index/migration can be Phase 2 if not yet present.

---

## 3) Database layer and migrations

Problems
- Mixed error handling (prints/None) and lack of context managers.
- Frequent connect/disconnect overhead without pooling.
- SQL strings scattered.
- verify_db_version present but not guaranteed to be enforced at startup.

Proposed changes
- Wrap DB operations with context managers and unify error signaling:
  - Introduce DatabaseError and a Result[T] (or raise exceptions with clear types).
- Add connection pooling (psycopg2.pool.SimpleConnectionPool) sized for local GUI use.
- Centralize SQL: move to hunter/queries.py or adopt SQLAlchemy Core while keeping psycopg2 option open.
- Migrations:
  - Ensure tools/run_migrations.py creates schema_version; apply ordered migrations.
  - At app start (python -m hunter), call db_manager.verify_db_version() and show a user-friendly GUI prompt to run migrations if out-of-date.
- Indices and constraints audit: verify presence per tasks.md #20.

Rationale
- Predictable error semantics and resource management improve stability; pooling reduces latency.

Risks/Assumptions
- Connection pool sizing must avoid exhausting local Postgres connections; start small (min=1, max=5).

Success criteria
- No unclosed connections; consistent exception types; startup blocks with actionable guidance if DB is not ready.

Phase
- Phase 1–2 (pooling may be Phase 2).

---

## 4) Configuration and secrets management

Problems
- config_manager eager-loads config.ini and exits if missing, harming tests and first-run UX.
- Secrets reside in config.ini without .env overrides.

Proposed changes
- Lazy-load configuration on first access; avoid sys.exit on import.
- Provide environment variable overrides and .env support.
- Add config.example.ini and .env.example with documented fields and defaults.
- Validate configuration schema on load; surface errors via GUI with remediation steps.

Rationale
- Better developer UX; safer secret handling; more flexible deployments.

Risks/Assumptions
- Some modules may rely on config values at import time; refactor to call getters.

Success criteria
- Importing modules in tests no longer exits; GUI provides clear setup flow when config is missing.

Phase
- Phase 1 for lazy-load; Phase 2 for .env + validation.

---

## 5) Logging and observability

Problems
- print statements in background threads; lack of structured logs.

Proposed changes
- Standardize on Python logging with:
  - Console handler and a GUI Text widget handler.
  - Structured formatter (key=value or JSON) for file/console; simplified formatter for GUI.
- Telemetry: add lightweight agent metrics table (start_time, end_time, status, count).

Rationale
- Improves debuggability and long-term operations insight.

Risks/Assumptions
- GUI logging must remain thread-safe (use queue + consumer thread + .after updates).

Success criteria
- Consistent log levels; test verifies background consumer alive and messages appear.

Phase
- Phase 1 for logging baseline; Phase 2 for telemetry.

---

## 6) Agents and dispatcher

Problems
- Inconsistent interfaces; lack of retries/timeouts; unclear plugin discovery; rate limiting not enforced.

Proposed changes
- Agent interface: hunt(source: Source, bookmark: str|None, limit: int) -> (list[Lead], str|None, str|None).
- Add per-agent timeouts and retry/backoff with sensible defaults; classify exceptions as retryable/non-retryable.
- Plugin registry: a central mapping {agent_type: callable} with validation of required credentials; safe fallback when optional deps absent.
- Rate limiting: per-source fields (max_concurrent, consecutive_failures, last_failure_date) enforced by dispatcher.
- Headless CLI entry point for non-GUI hunts.
- Cancellable background tasks (thread flag or futures) wired to GUI.

Rationale
- Predictable, safe, and extensible agent execution.

Risks/Assumptions
- Third-party libraries (e.g., praw) might be missing; ensure graceful disable with logs.

Success criteria
- Dispatcher covers: no active sources, agent success with new bookmark, failure path, duplicate filtering, DB state updates; all tested.

Phase
- Phase 1–2.

---

## 7) GUI/UX and threading

Problems
- Potential off-main-thread widget updates; limited error feedback.

Proposed changes
- Audit UI updates; ensure .after scheduling for thread-originated events.
- Add non-blocking toast/status bar messaging; color-coded logs already exist—add filtering and copy-to-clipboard.
- Triage UX: sorting, filtering by source/score/date, bulk operations with progress.
- HTML rendering safety in embedded browser: disable JS; open external links in system browser; whitelist protocols.
- Ops dashboard for agent metrics (if telemetry enabled).

Rationale
- Keeps GUI responsive and safe; improves operator efficiency.

Success criteria
- No Tkinter exceptions from background threads; observable improved triage interactions.

Phase
- Phase 2–3.

---

## 8) Domain modeling and type safety

Problems
- Dict-based data prone to key errors; sparse type hints and docstrings.

Proposed changes
- Introduce dataclasses or Pydantic models for Lead and Source with validated fields (UTC-aware datetimes, normalized URLs).
- Centralize constants/enums for statuses, agent types, table names.
- Add comprehensive type hints; enable mypy with a strict-enough config.
- Add docstrings on public functions/classes.

Rationale
- Reduces runtime errors; improves IDE support and refactor safety.

Success criteria
- mypy passes at chosen strictness; fewer KeyErrors in runtime.

Phase
- Phase 2.

---

## 9) Testing strategy

Principles
- Hermetic, fast, and deterministic tests; mock external dependencies.

Proposed changes
- Unit tests
  - Dispatcher behaviors (no sources, success w/ bookmark, failure, duplicate filtering, DB state updates).
  - db_manager functions using a temp test DB (testcontainers or docker-compose) or a stubbed layer.
  - HTML sanitizer and link extractor.
- Integration tests
  - Simulate a full hunt cycle with mocked agent results; verify persistence.
- Tooling
  - pytest configuration (pytest.ini) for collection and coverage; maintain unittest compatibility for existing tests.
  - Coverage thresholds; run in CI.
- Testing tips
  - Patch hunter.db_manager.get_db_connection; patch config access to avoid fatal exits.

Success criteria
- CI shows green with coverage meeting thresholds; tests run without a live network.

Phase
- Phase 1–2 (unit first, integration next).

---

## 10) Security, privacy, and compliance

Proposed changes
- SECURITY.md and logging redaction of secrets; never log tokens.
- CODE_OF_CONDUCT.md; issue/PR templates.
- Rate limiting and backoff to be friendly to upstream sources.

Success criteria
- No secrets in logs; documented vulnerability reporting path.

Phase
- Phase 2.

---

## 11) Developer experience, packaging, and documentation

Proposed changes
- Pre-commit hooks: black, isort, flake8, mypy; consistent formatting.
- Audit requirements.txt; pin versions; extras for optional agents; consider pyproject.toml.
- Documentation: architecture.md (with diagram), expanded README (setup, migrations, API keys), ROADMAP.md.
- Windows packaging guidance (PyInstaller/Briefcase) and a launcher shortcut.
- Nightly maintenance job for cache/log rotation and DB vacuum.
- Feature flags to toggle agents and debug UI.

Success criteria
- Onboarding time reduced; reproducible builds; clear docs for contributors.

Phase
- Phase 2–3.

---

## Phased roadmap

Phase 1 — Stabilization and correctness (Weeks 1–2)
- Align dispatcher and DB APIs; standardize agent return type.
- Central dedup function and URL normalization (in code; DB later if needed).
- Switch to logging with console + GUI handler; keep queue-based consumer.
- Make config_manager lazy-load and non-fatal; provide clear GUI message if missing.
- Add core unit tests for dispatcher and critical db_manager paths.
- Wire verify_db_version into startup with friendly prompt.

Exit criteria: End-to-end hunt succeeds locally; tests pass; no fatal import exits.

Phase 2 — Architecture, performance, and safety (Weeks 3–5)
- DB connection pooling; centralized SQL; indices/constraints audit and migrations.
- Domain models (Lead, Source); constants/enums; mypy enabled; docstrings.
- Retry/backoff, timeouts, safe fallbacks for agents; plugin registry.
- Security improvements (redaction), telemetry table and Ops view baseline.
- Documentation: architecture.md, expanded README, SECURITY.md, contribution standards; pre-commit hooks.

Exit criteria: Stable runs over days with low error rates; type checks clean; docs in place.

Phase 3 — UX and extensibility (Weeks 6–8)
- Triage UX enhancements; toast/status; copy-to-clipboard and filters.
- Safe HTML rendering; headless CLI; cancellable hunts.
- Packaging guidance; feature flags; nightly maintenance.
- Roadmap.md with upcoming agents (RSS, Hacker News, Twitter/X), multi-user, backend API.

Exit criteria: Positive operator feedback; headless mode usable; packaging guide validated.

---

## Success metrics
- Functional: zero unhandled exceptions during hunts; idempotent dedup; accurate source state updates.
- Quality: test coverage ≥ 70% (ratcheting up later), mypy clean, pre-commit green.
- Performance: hunt cycle times reduced by ≥ 20% from baseline due to pooling and API alignment.
- UX: GUI remains responsive under load; user-visible error messages actionable.
- Ops: structured logs available; telemetry dashboards show agent durations and outcomes.

---

## Risks and mitigations
- Risk: Refactors break existing agents. Mitigation: keep shims for deprecated interfaces and add adapter tests.
- Risk: Pooling increases connection usage. Mitigation: conservative pool sizes; close on shutdown.
- Risk: Config lazy-load changes import-time behavior. Mitigation: stage behind feature flag during transition; thorough tests.

---

## Appendix: Mapping to docs/tasks.md
- 1–5: API alignment and dedup — sections 1 and 2.
- 6: Missing modules — covered in sections 7 and 8 (domain/utilities) with safe fallbacks.
- 7–9: Logging — section 5.
- 10: DB error handling — section 3.
- 11–15: Type hints/docstrings/timezone/datamodel — sections 2 and 8.
- 16–17: Timeouts/backoff/error handling — section 6.
- 18–21: Pooling/queries/migrations/version checks — section 3.
- 22–24: Config lazy-load/env/.env examples — section 4.
- 25–28: Service layer, plugin registry, cancellable tasks, main-thread UI — sections 6 and 7.
- 29–35: Tests and CI — section 9.
- 36: Headless CLI — section 6 and 7.
- 37–39: GUI feedback/triage/HTML safety — section 7.
- 40–41: Telemetry/rate limiting — section 6 and 5.
- 42–45: Constants/dataclasses/acquisition idempotency/URL normalization — sections 2 and 8.
- 46–49: Optional deps fallback/tools and verify flow — sections 3, 6, 7.
- 50–53: Documentation and community — section 11.
- 54–56: Maintenance job/feature flags/telemetry table — sections 5 and 11.
- 57–60: Graceful shutdown/packaging/LICENSE/roadmap — sections 7 and 11.
