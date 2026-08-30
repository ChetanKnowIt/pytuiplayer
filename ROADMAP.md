# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Design Flaws (open)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 9 | _Closed by feature/04._ `load_local_files` now uses `os.walk` for recursive scan. | `tui_app.py:254-305` | Nested music folders now supported |

---

## Test Inventory (in `testsuite.db`)
The full test inventory — including the test backlog (missing/integration tests) and their
done/pending status — lives **exclusively** in a structured SQLite database
(`testsuite.db` at the repo root). ROADMAP.md stays light; the DB is the single source of
truth for everything test-related. As features are added, every `uv run pytest` run refreshes
it, so the Test Backlog doubles as the **prerequisite checklist** before starting the next
feature.

- **Schema:** `files`, `tests`, `runs`, `backlog`, `meta` (see
  `src/tests/testsuite_db.py`). Upsert keyed on `(file, name)` — reruns are idempotent.
- **Auto-refresh:** every `uv run pytest` run writes the `tests` + `runs` tables via
  the hook in `src/tests/conftest.py`.
- **Enrichment:** `scripts/update_testsuite_db.py` refreshes `files` (line counts +
  descriptions) and mirrors the Test Backlog into `backlog` (status preserved).
- **Reporting:** `scripts/report_testsuite_db.py` prints the inventory / backlog / runs.

```bash
uv run pytest -q                       # runs tests AND refreshes testsuite.db
uv run python scripts/update_testsuite_db.py   # enrich files + sync backlog
uv run python scripts/report_testsuite_db.py    # print the inventory
```

```sql
-- Quick queries against testsuite.db
SELECT file, COUNT(*) AS n FROM tests GROUP BY file ORDER BY file;
SELECT status, COUNT(*) FROM backlog GROUP BY status;          -- done vs pending
SELECT * FROM runs ORDER BY id DESC LIMIT 5;                   -- last runs
```

> The `network`-marked radio test (`test_radio_integration.py`) passes when a live
> stream is reachable and auto-skips offline.

---

## Feature Plan (branch-organized)

Open work is grouped into feature branches. Each branch is developed and tested on
its own (`feature/NN-slug`), and may merge to `main` only when every test in its plan
passes (`uv run pytest -q` → green) and `uv run ruff check .` is clean. The test names
below are the **acceptance criteria** — add them to `src/tests/` (e.g.
`test_feature_0N_*.py`) and mirror them into `testsuite.db` via
`scripts/update_testsuite_db.py` so the DB tracks each branch's progress.

### feature/04-update-medium-priority — **DONE** (branch `feature/04-update-medium-priority`)
Closes Medium Priority #1 (recursive directory scanning); remaining medium items are
unscheduled follow-ups.

**Tests required to mark Done (all pass — 5 tests in `test_feature_04_medium_priority.py`):**
- ✅ `test_load_local_files_recursive` — `load_local_files` walks subdirectories (temp tree
  with nested `.mp3`s); all appear in the local list and respect `max_playlist_items` +
  batched mounting. Supporting: `test_load_local_files_recursive_respects_max_playlist_items`,
  `test_load_local_files_recursive_batched_mounting`, `test_load_local_files_top_level_still_works`.

Follow-up medium items (playlist search/filter, station favorites, playback history,
shuffle/repeat, configurable bindings, playlist export, album art) remain unscheduled and
may be split into their own `feature/0N-*` branches as they are scheduled.

### Low Priority (unscheduled — revisit after 04)
1. Add playlist search/filter — type to filter local list
2. Add station favorites — bookmark frequently played stations
3. Add playback history — track recently played items
4. Add shuffle/repeat modes — standard player features
5. Add configurable keybindings — user-defined bindings
6. Add playlist export — save current list as M3U
7. Add album art / visualizer — ASCII art from audio

---

## Notes

- Run `uv run pytest -q` before and after changes — expect 80 passed (last run: 2026-08-30 on branch `feature/04-update-medium-priority`)
- Run `uv run ruff check .` for linting
- All tests use `FakeMPV` injection pattern — maintain this for new tests
- `PYTUIP_DEBUG=1` enables stack traces on `update_now_playing` calls
- `PYTUIP_PROFILE=1` enables performance profiling (logs to `pytuiplayer.performance`)
- `_meta_label` is set on items by `load_m3u` but NOT by `load_local_files`
- `load_stations_ui()` exists at line 882 — test at line 55 uses it correctly
- **Pitfall #16 (run_worker arg binding):** Textual's `App.run_worker(work, name="", ...)` takes the
  worker *name* as its 2nd positional — it does NOT forward extra positionals to `work`. To pass args,
  bind them: `self.run_worker(functools.partial(self.fetch_duration, item), name=..., exit_on_error=False)`.
  The old `run_worker(self.fetch_duration, item)` passed `item` as `name`, so `fetch_duration()` ran with
  no `item` and crashed the TUI (TypeError) when switching Radio→Local. Set `exit_on_error=False` so a
  tag-read failure can't kill the app.

### Entry point / launch (fixed)
- `uv run pytuiplayer` (console script `pytuiplayer = "pytuiplayer:main"`) now launches the real TUI: `pytuiplayer/__init__.py:main` lazily imports `MusicPlayerApp` and calls `.run()`. Previously `__init__.py:main` was a `print("Hello")` stub, so the console script exited without launching the UI. `python -m pytuiplayer` (via `__main__.py`) always worked.
- Do NOT change the entry point to `pytuiplayer.__main:main`: under this project's editable `uv_build` install, `pytuiplayer.__main` is not importable as a submodule (`import pytuiplayer.__main` fails), so the script target would not resolve. Keep the launcher reachable from `pytuiplayer:main`.
- Running the module file directly (`uv run src/pytuiplayer/tui_app.py`) intentionally does nothing — `tui_app.py` has no `__main__` guard (by design; use the console script or `-m`).

### Scripts / manual demos (not part of the pytest suite)
- `scripts/run_radio_demo.py` — headless launch + start a radio stream (live network).
- `scripts/run_tui_app_demo.py` — headless launch; asserts the TUI mounts, loads stations, and renders the Now Playing widget (no playback).

---

## Workflow / Branching Policy

Every feature (and every non-trivial change) is developed on its **own independent branch** and must satisfy the quality gate below before it can be merged to `main`.

- **Branch per feature:** create a dedicated branch for each feature/bugfix (e.g. `feature/NN-short-slug`). Do not pile unrelated work onto one long-lived branch.
- **Tests are the merge gate:** a branch may only move to `main` after `uv run pytest -q` passes — **all tests green, no skips expected on a working machine** (the `network`-marked radio test is allowed to skip only when offline).
- **Lint gate:** `uv run ruff check .` must pass with no errors before merge.
- **One feature = one branch = one reviewable change.** Keep branches focused; split large efforts into smaller, independently-mergeable branches where possible.
- **No merge to `main` with failing tests or lint.** If a test must change, the change and its rationale travel together in the same branch.
- **Document as you go:** update `ROADMAP.md` (mark items Done / add backlog) and `docs/AI_TASK_STATE.md` within the branch so the merge carries its own status.

### Prepare to Commit Checklist (run before committing on a feature branch)

Run these to ensure the commit is reviewable and the merge will be clean:

1. **Tests pass:** `uv run pytest -q` → all passed (the `network` radio test may skip only when offline).
2. **Lint clean:** `uv run ruff check .` → `All checks passed!`
3. **Test count sanity:** verify the passed count matches expectations (no accidental triple-counting from conftest hooks).
4. **Testsuite DB report clean:** `uv run python scripts/report_testsuite_db.py` → verify:
   - `passed` count matches actual test count (not inflated by setup/call/teardown double-counting)
   - All new test files have descriptions (non-zero `lines` count)
   - Backlog items correctly reflect done/pending status
5. **Review acceptance tests:** each feature's acceptance tests cover the feature's behavior (not just importability).
6. **Scripts/demos work:** `uv run python scripts/run_tui_app_demo.py` and `uv run python scripts/run_radio_demo.py` boot cleanly.
7. **Docs in sync:** `ROADMAP.md` and `docs/AI_TASK_STATE.md` reflect the branch's work.

### Merge / Release Checklist (run before merging a feature branch into `main`)

Run these from the feature branch (and re-run on `main` after the merge) so the next
feature build always starts from a green, known-good state:

1. **Sync:** `git fetch` and ensure `main` has no unmerged commits that conflict
   (`git rev-list --count main..origin/main` → `0`).
2. **Lint gate:** `uv run ruff check .` → `All checks passed!`
3. **Test gate:** `uv run pytest -q` → all passed (the `network` radio test may skip
   only when offline; everything else must be green).
4. **Type/import sanity (optional):** `uv run python -c "import pytuiplayer"` and
   `uv run pytuiplayer` (or `uv run python scripts/run_tui_app_demo.py`) boot cleanly.
5. **Docs in sync:** `ROADMAP.md` and `docs/AI_TASK_STATE.md` reflect the branch's work.
6. **Merge:** `git checkout main && git merge --no-ff feature/<slug>` (the `--no-ff`
   keeps a visible feature boundary in history), then `git push origin main`.
7. **Post-merge verify:** re-run steps 2–3 on `main` to confirm the merge is green.
8. **Next feature:** start the new work on a fresh branch off updated `main`
   (`git checkout main && git pull && git checkout -b feature/<next-slug>`).

> History note: `feature/01-song-duration`, `feature/02-fix-design-flows`, `feature/03-fix-missing-features`,
> and `feature/04-update-medium-priority` have been merged to `main` and pushed. `main` is the
> known-good baseline for the next feature branch.
