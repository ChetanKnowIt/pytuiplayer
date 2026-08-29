# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Design Flaws

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 4 | No Screen abstraction — mode switching via manual visibility/disabled toggling | `tui_app.py:348-390,463-518` | Brittle, repetitive, error-prone |
| 5 | `update_now_playing` dual path (post_message + direct assignment fallback) | `tui_app.py:900-926` | Confusing control flow; hard to debug |
| 6 | `item.data` shape varies: dict (M3U), dict (local), raw station dict (radio) | Throughout | Requires `isinstance` checks everywhere |
| 7 | Imports inside method bodies (`asyncio`, `Path`, `DirectoryTree`) | `tui_app.py` (was 745-748) | Resolved — hoisted to module top |
| 8 | Silent exception swallowing (`try/except: pass`) in most methods | Throughout | Makes debugging extremely difficult |
| 9 | `load_local_files` only scans top-level directory — no recursive scan | `tui_app.py:532-548` | Nested music folders not supported |
| 10 | ProgressBar bar width hardcoded to 160 chars | `tui_app.py:242` | Not responsive to terminal width |

### Missing Features / Gaps

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 11 | No metadata fetching for local files (only radio ICY) | `_refresh_metadata` | Local files show filename only |
| 12 | `action_play_playlist` relies on `items` attribute that ListView lacks | `tui_app.py:1192-1210` | Falls back to `children`; fragile |
| 13 | No keyboard binding for `action_play_playlist` | `BINDINGS` | Feature exists but is inaccessible |

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

## Feature Backlog

### High Priority

No open High Priority work remains — the original items (fix `fetch_duration` decorator,
single `max_playlist_items` source of truth, `_populate_missing_durations` Path handling,
hoist imports to module top) were completed in the `feature/01-song-duration` merge
(`6b417cb`). New features should start from a green `testsuite.db` (run `uv run pytest`,
confirm 0 failed) and add their tests to the backlog before implementation. See Medium/Low
Priority for upcoming features.

### Medium Priority

1. Add recursive directory scanning — `load_local_files` should walk subdirs
2. Add local file metadata polling — show tags during playback
3. Make ProgressBar responsive — use widget size instead of hardcoded 160
4. Add Screen abstraction — separate RadioScreen and LocalScreen
5. Add playlist playback keyboard binding — e.g. `Enter` to play playlist
6. Unify `item.data` shape — standardize on `{"source", "title", "duration", "meta"}`

### Low Priority

1. Add playlist search/filter — type to filter local list
2. Add station favorites — bookmark frequently played stations
3. Add playback history — track recently played items
4. Add shuffle/repeat modes — standard player features
5. Add configurable keybindings — user-defined bindings
6. Add playlist export — save current list as M3U
7. Add album art / visualizer — ASCII art from audio

---

## Refactoring Candidates

1. Split `tui_app.py` — Extract widgets, event handlers, and loaders into separate modules
2. Create `utils.py` — Move `_parse_extinf`, `_resolve_source`, `fmt_mmss` helpers
3. Create `constants.py` — Move `MAX_PLAYLIST_ITEMS`, `ICON_OK`, `ICON_ERR`
4. Standardize error handling — Replace bare `except: pass` with structured logging
5. Add type hints — `item.data` needs TypedDict or dataclass

---

## Notes

- Run `uv run pytest -q` before and after changes — expect 53 passed (last run: 2026-08-30 on branch `testsuite/01-update-test-backlog`)
- Run `uv run ruff check .` for linting
- All tests use `FakeMPV` injection pattern — maintain this for new tests
- `PYTUIP_DEBUG=1` enables stack traces on `update_now_playing` calls
- `PYTUIP_PROFILE=1` enables performance profiling (logs to `pytuiplayer.performance`)
- `_meta_label` is set on items by `load_m3u` but NOT by `load_local_files`
- `load_stations_ui()` exists at line 882 — test at line 55 uses it correctly

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

> History note: `feature/01-song-duration` was merged to `main` (merge commit `6b417cb`)
> and pushed. After that, `main` is the known-good baseline for the next feature branch.
