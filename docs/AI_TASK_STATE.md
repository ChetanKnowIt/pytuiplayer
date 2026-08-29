# AI_TASK_STATE.md

## Current Branch
`testsuite/01-update-test-backlog` (branched off `main` @ `774c209`, known-good baseline: 31 tests, ruff clean)

## Purpose
1. Create and close every test in the ROADMAP "Test Backlog" as Done, and review the existing
   suite as useful/functional on the current code.
2. Move the verbose markdown Test Inventory out of ROADMAP.md into a structured SQLite
   `testsuite.db`, and wire it to refresh on every `uv run pytest` run so it stays reusable
   for upcoming features.

## Completed This Session

### A. Test backlog closed (previous step)
- Added `src/tests/test_backlog_coverage.py` (22 tests) covering ROADMAP Test Backlog
  Missing Unit Tests #2-#20 + Integration/Widget Tests #1-#4. Full suite = 53 passed.
- Marked every backlog item ✅ Done in ROADMAP.md.

### B. SQLite test inventory (this step)
New files:
- `src/tests/testsuite_db.py` (stdlib-only: `sqlite3`, `pathlib`, `datetime`, `json`).
  Schema: `files(file, description, line_count)`, `tests(name, file, description, line, markers)`
  keyed `(file,name)`, `runs(id, started_at, pytest_exit, collected, passed, failed, skipped,
  errors, duration_s, branch, python_version, note)`, `backlog(name, kind, description, status,
  source)`, `meta(key, value)`. Upserts are idempotent. Helper API: `connect`, `upsert_file`,
  `ensure_file`, `clear_tests_for_file`, `upsert_test`, `record_run`, `upsert_backlog`,
  `discover_tests`, `count_lines`, `summary`.
- `scripts/update_testsuite_db.py` — enriches `files` (line counts + descriptions) and mirrors
  the ROADMAP Test Backlog into `backlog`. `--reset-backlog` recreates backlog rows from the
  built-in list; status is otherwise **preserved** across runs (never auto-flipped to pending).
- `scripts/report_testsuite_db.py` — prints summary / per-file / backlog / last-run records.
  Flags: `--by-file`, `--backlog`, `--last-run`.

Wiring:
- `src/tests/conftest.py` — added `pytest_sessionfinish` hook (best-effort, never fails the
  suite) that upserts each collected test into `tests` (with real line numbers via
  `item.location`) and appends a row to `runs` (counts from `pytest_runtest_logreport`, plus
  git branch + python version). So every `uv run pytest` refreshes `testsuite.db`.
- `.gitignore` — added `testsuite.db` / `testsuite.db-*` (generated artifact, not committed).
- `ROADMAP.md` — replaced the ~100-line inline per-file Test Inventory with a compact
  "Test Inventory (in `testsuite.db`)" section: schema pointers, the three commands, and
  copy-paste SQL queries. Backlog ✅ statuses remain in the lighter `backlog` table view.

### Docs updated
- ROADMAP.md: lightened (Test Inventory now DB-backed); backlog items already ✅.

### Finalization (ROADMAP.md trimmed to forward-looking only)
Per user direction, removed all *done/fixed* history from ROADMAP.md so it stays a
forward-looking roadmap:
- Deleted the **Critical Bugs** section entirely (all 3 were fixed in `feature/01-song-duration`).
- Deleted the **Test Backlog** section (Missing Unit Tests #1-#20 + Integration/Widget #1-#4)
  — this now lives **exclusively** in `testsuite.db` (the `backlog` table, refreshed by
  `scripts/update_testsuite_db.py`). ROADMAP.md carries only a pointer to it.
- Removed the historical "Infrastructure (Completed)" table and the "✅ Fixed"/"Done" noise
  from Design Flaws row #7.
- Reframed the **Test Inventory (in `testsuite.db`)** intro: the DB is the *single source of
  truth* for everything test-related, and the (DB-tracked) Test Backlog is now the
  **prerequisite checklist** before starting the next feature.
- **Feature Backlog** is the next phase of focus; its High Priority note now states new
  features start from a green `testsuite.db` and add tests to the backlog before implementation.
- Design Flaws, Missing Features, Medium/Low Priority, Refactoring Candidates, Notes, and
  Workflow sections are retained as the active roadmap.

### Docs updated (final)
- ROADMAP.md: trimmed to forward-looking content only; test backlog lives in testsuite.db.
- AGENTS.md: updated for future use (counts, schema, DB refresh, current line numbers).
- README.md: fixed verification count (53 passed) + DB refresh note.
- AI_TASK_STATE.md: this entry.

## Tests
- `uv run pytest -q` → **53 passed in ~8.8s**; the run also refreshes `testsuite.db`
  (`tests` + `runs` tables). 24/24 backlog rows marked done.
- `uv run python scripts/update_testsuite_db.py` → refreshes `files` (8 modules) + syncs 24 backlog rows.
- `uv run python scripts/report_testsuite_db.py` → prints inventory/backlog/runs correctly.
- `uv run ruff check .` → All checks passed.

## Remaining
- None for this branch. ROADMAP.md is lighter; the inventory is now queryable/reusable.
- Awaiting user decision on merging `testsuite/01-update-test-backlog` into `main`.

## Architectural Decisions
- `testsuite.db` is a *cache of the last pytest run*, not a source of truth; the conftest hook
  and the manual script are the only writers. Re-running is idempotent (upsert on `(file,name)`
  and `name`).
- The pytest hook uses `ensure_file` (INSERT OR IGNORE) for `files` so it never clobbers the
  richer descriptions written by `scripts/update_testsuite_db.py`; the manual script owns
  `files.description`/`line_count` and `backlog` rows.
- The conftest hook is wrapped in try/except and prints a WARNING on failure so the DB refresh
  can never break the actual test suite (per the repo's defensive-TUI philosophy).
- `session.session.items` is iterated to capture all test nodes; `item.location[1]+1` gives the
  1-based source line.
- Markers are captured as a JSON array for future filtering (e.g. the `network` radio test).

## Next Step
Branch complete and green. Optionally merge to `main` if requested (do NOT merge unless asked).
