# Hunters_Bunker Improvement Tasks Checklist

Note: Each item is actionable and ordered to prioritize correctness and stability first, then architecture, quality, performance, UX, and documentation. Check off [x] as you complete tasks.

1. [ ] Resolve dispatcher/DB API mismatches between actions_news_search.py and hunter/db_manager.py (rename or adapt functions consistently). Specifically align check_acquisition_log vs check_acquisition_router and update_source_check_time vs update_source_state.
2. [ ] Standardize agent hunt() return type across all search_agents (tuple vs list). Decide on a canonical interface (e.g., (leads: list[Lead], new_bookmark_id: str|None)) and update dispatcher and all agents to match.
3. [ ] Update actions_news_search.search_all_sources to correctly handle the standardized agent return type and propagate success/failure state to db_manager.update_source_state.
4. [ ] Ensure actions_news_search filters duplicates consistently. Replace URL-only checks with UUID-first or normalized URL hash strategy aligned with acquisition_router schema.
5. [ ] Implement a single deduplication function in db_manager or a domain service (e.g., is_duplicate_lead(lead) -> bool) and use it in the dispatcher instead of scattered checks.
6. [ ] Add missing module(s) referenced by hunter_app.py imports: .html_parsers.link_extractor and .custom_widgets.tooltip. Either create or replace with existing utilities to avoid ImportError at runtime.
7. [ ] Review hunter/utils.py usage; integrate with standard logging instead of bare print to console from background threads.
8. [ ] Replace print statements across the codebase with Python logging, set up a logger with handlers for GUI (Tkinter Text/CTkTextbox) and console, and appropriate levels.
9. [ ] Introduce structured log formatting (JSON or key=value) for machine-parsable logs; provide a simple formatter for GUI readability.
10. [ ] Refactor db_manager to use context managers and consistent error propagation (raise custom exceptions or return Result objects) instead of mixed prints/None.
11. [ ] Add type hints across hunter_app.py, db_manager.py, actions_news_search.py, utils.py, and agents; enable mypy with a strict-enough config.
12. [ ] Add docstrings with clear parameter/return types and side effects for all public functions and classes.
13. [ ] Normalize timezone handling to always use timezone-aware UTC datetimes (ensure all DB writes and comparisons use UTC; document expectations in code).
14. [ ] Introduce a domain model for Source and Lead (dataclasses or Pydantic models) to reduce dict key mistakes and improve type safety.
15. [ ] Validate and sanitize inputs from external sources (e.g., URLs, titles, HTML) before persistence or rendering; centralize in a validation module.
16. [ ] Add network request timeouts and retry/backoff to agents (requests for GNews, PRAW has built-ins; still enforce sensible timeouts).
17. [ ] Add graceful error handling around external APIs (map exceptions to retryable/non-retryable outcomes; surface user-friendly messages in GUI).
18. [ ] Implement connection pooling for PostgreSQL (psycopg2.pool or migrate to SQLAlchemy Engine) to avoid frequent connect/disconnect overhead.
19. [ ] Move SQL strings to a queries module or use SQLAlchemy Core to improve maintainability and reduce duplication.
20. [ ] Ensure DB indices and constraints support access patterns (unique on (url, publication_date) exists; also index lead_uuid, source_id, last_checked_date, last_known_item_id).
21. [ ] Add a migration runner tool (tools/run_migrations.py) or adopt Alembic; ensure schema_version table is enforced and verified on startup (db_manager.verify_db_version is present—wire it into startup flow and GUI).
22. [ ] Make config_manager lazy-load and non-fatal when config.ini is missing; provide a helpful startup dialog in GUI with steps to configure.
23. [ ] Support environment variable overrides and .env file for secrets; remove secrets from config.ini if possible; provide config schema validation.
24. [ ] Provide a .env.example and a config.example.ini with documented fields and defaults.
25. [ ] Decouple GUI from business logic: introduce an application service layer that the GUI calls (e.g., CaseService, HuntService) to simplify threading and testing.
26. [ ] Introduce a plugin registry for agents (mapping agent_type -> callable) with discovery mechanism (entry points or registry module) and validation of required credentials.
27. [ ] Implement a cancellable background task mechanism for hunts (thread flag or concurrent.futures with cancellation); wire to GUI buttons.
28. [ ] Ensure all Tkinter UI updates happen on the main thread (audit usages of after and direct widget access from threads).
29. [ ] Add unit tests for dispatcher behavior, including: no active sources; agent success with new bookmark; agent failure path; duplicate filtering; DB state updates.
30. [ ] Add unit tests for db_manager functions using a temporary test DB (docker-compose or testcontainers) with isolated schema and teardown.
31. [ ] Add unit tests for html_parsers.html_sanitizer.sanitize_and_style and any link_extractor implementation (malicious HTML, inline styles, script tags, title duplication logic).
32. [ ] Add integration tests that simulate a full hunt cycle: seed sources, mock agent results, run dispatcher, verify cases and logs persisted.
33. [ ] Add pytest configuration (pytest.ini) and code coverage with thresholds; integrate with CI.
34. [ ] Set up pre-commit hooks (black, isort, flake8, mypy) and format codebase; add a CONTRIBUTING.md explaining standards.
35. [ ] Audit requirements.txt; pin versions; add extras for optional agents (e.g., reddit); consider moving to pyproject.toml with Poetry or PEP 621 metadata.
36. [ ] Add a CLI entry point for running hunts headless (python -m hunter or console_script), separate from GUI startup.
37. [ ] Improve error feedback in GUI: show non-blocking toast or status line for failures; color-coded log entries already exist—extend with filtering and copy-to-clipboard.
38. [ ] Enhance triage UX: sorting, filtering by source/score/date, select-all/none, and batch operations with progress indicator.
39. [ ] Sanitize and render HTML safely in embedded browser (tkinterweb): ensure external links open in system browser; disable JS; whitelist protocols.
40. [ ] Add telemetry around agent runtimes and success/failure rates; visualize in an Ops tab within the GUI.
41. [ ] Implement rate limiting and backoff per source in the DB (max_concurrent_requests, last_failure_date, consecutive_failures) and enforce in dispatcher.
42. [ ] Centralize constants and magic strings (statuses like TRIAGED, table names, agent types) into enums or a constants module.
43. [ ] Replace scattered string keys ('source_name', 'last_checked_date', etc.) with typed attributes on dataclasses to reduce KeyError risk.
44. [ ] Harden acquisition logging: ensure idempotency on re-runs; use ON CONFLICT consistently; wrap multi-statement writes in transactions.
45. [ ] Add URL normalization and canonicalization (strip UTM params, normalize scheme/host) before deduplication and persistence.
46. [ ] Provide a safe fallback when external dependencies are missing (e.g., if praw not installed, disable reddit agent with a clear log).
47. [ ] Improve tools scripts (tools/case_seeder.py, tools/bootstrap_case_data.py) to be idempotent, parameterized, and use shared db_manager functions.
48. [ ] Wire db_manager.verify_db_version into HunterApp startup with a user-friendly message and button to open migration tool.
49. [ ] Introduce configuration for per-agent parameters (limits, languages, regions) in DB or config; validate before running.
50. [ ] Document architecture (layers, modules, data flow) and provide a diagram in docs/architecture.md; link from README.
51. [ ] Expand README with setup instructions (DB config, migrations, API keys), troubleshooting, and common tasks.
52. [ ] Add SECURITY.md with guidance on reporting vulnerabilities and handling secrets; redact sensitive data in logs.
53. [ ] Add CODE_OF_CONDUCT.md and issue/PR templates to standardize contributions.
54. [ ] Add a nightly maintenance job/task (cron or scheduled) to prune old cache, rotate logs, and vacuum relevant DB tables.
55. [ ] Introduce feature flags (env or config) for enabling/disabling agents and debug UI.
56. [ ] Implement a small telemetry DB table for agent metrics and surface in an Ops dashboard in the GUI.
57. [ ] Add graceful shutdown handling for background threads and DB connections when GUI closes.
58. [ ] Provide Windows-specific packaging guidance (PyInstaller/Briefcase) and a launcher shortcut for end users.
59. [ ] Ensure license headers are consistent; add a LICENSE file if missing and reference in all modules.
60. [ ] Create a ROADMAP.md outlining planned agents (RSS, Hacker News, Twitter/X), backend API, and multi-user support.
