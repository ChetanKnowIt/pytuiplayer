# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Design Flaws (open)

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 9 | `load_local_files` only scans top-level directory — no recursive scan | `tui_app.py:532-548` | Nested music folders not supported |

### Missing Features / Gaps

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| — | _None open._ #11 (local metadata), #12 (playlist item access), #13 (playlist binding) closed by `feature/03-fix-missing-features`. | — | — |

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
`test_feature_03_missing_features.py`) and mirror them into `testsuite.db` via
`scripts/update_testsuite_db.py` so the DB tracks each branch's progress.

### feature/03-fix-missing-features — **DONE** (branch `feature/03-fix-missing-features`)
Closes Missing Features / Gaps #11, #12, #13.
Functional gaps: local-file metadata, robust playlist item access, playlist keyboard binding.

**Tests required to mark Done (all pass — 10 tests in `test_feature_03_missing_features.py`):**
- ✅ `test_local_metadata_polling_updates_title` — `_refresh_metadata` delegates to
  `_refresh_local_metadata` in local mode, reads mutagen tags (`artist - title`) and updates
  `current_title` / `NowPlaying`. Supporting: `test_local_metadata_polling_is_cached_per_source`,
  `test_local_metadata_falls_back_to_media_title`, `test_radio_metadata_path_still_works`,
  `test_play_local_records_current_source`.
- ✅ `test_action_play_playlist_resolves_item` — resolution moved to
  `_resolve_playlist_items()` (tries `items`, then `children`, never raises). Supporting:
  `test_action_play_playlist_without_items_attribute`, `test_resolve_playlist_items_never_raises`,
  `test_action_play_playlist_reports_empty_playlist`.
- ✅ `test_playlist_keyboard_binding_plays` — `Binding("o", "play_playlist")` added to
  `BINDINGS`; the action plays the first playlist item via mpv.

**Bug fix (added in-session): M3U radio URL entries shown as "Local File", no metadata.**
- Root cause: `play_local` routed M3U URL entries through its URL branch, which set
  `currently_playing = "local"` and labeled the source `"Local File"`; `_refresh_metadata`
  only polled streams when `option_mode == "radio"`, so an M3U playlist of radio URLs was
  never metadata-polled and was mislabeled.
- Fix: introduced a `_stream_source` flag (True for any network stream — live radio or an
  M3U URL entry). `_refresh_metadata` now dispatches on `_stream_source`
  (`_refresh_stream_metadata` for icy-title/`media-title`) vs `currently_playing == "local"`
  (`_refresh_local_metadata` for mutagen tags). `play_local`'s URL branch sets
  `_stream_source = True` and labels the entry `"Radio"`; the filesystem branch sets it
  False. `action_stop` clears it. Progress-bar title display also keys off `_stream_source`.
- Tests: `test_play_local_url_is_flagged_stream`, `test_play_local_url_polls_stream_metadata`,
  `test_play_local_filesystem_is_not_stream`, `test_stop_clears_stream_flag`,
  `test_update_progress_meta_uses_stream_source`. Pre-existing radio/progress tests updated
  to set `_stream_source = True`. Dataset-driven coverage added using the real
  `src/tests/assets/radio_stations_hq.m3u` (177 stations, CRLF, `:` in titles):
  `test_load_real_radio_m3u_populates`, `test_real_radio_m3u_entries_play_as_streams`.

### feature/04-update-medium-priority
Closes Medium Priority #1 (recursive directory scanning) and any medium items not already
delivered by 02/03.
Note: Medium #2 (local metadata), #3 (responsive bar), #4 (Screen abstraction), #5
(playlist binding), #6 (unify `item.data`) are delivered by feature/02/03 above, so this
branch owns the remaining net-new medium features — starting with recursive scan.

**Tests required to mark Done (all must pass):**
- `test_load_local_files_recursive` — `load_local_files` walks subdirectories (build a
  temp tree with nested `.mp3`s); all appear in the local list and respect
  `max_playlist_items` + batched mounting.
- Follow-up medium items (playlist search/filter, station favorites, playback history,
  shuffle/repeat, configurable bindings, playlist export, album art) will be appended here
  or split into their own `feature/0N-*` branches as they are scheduled.

### Low Priority (unscheduled — revisit after 02–04)
1. Add playlist search/filter — type to filter local list
2. Add station favorites — bookmark frequently played stations
3. Add playback history — track recently played items
4. Add shuffle/repeat modes — standard player features
5. Add configurable keybindings — user-defined bindings
6. Add playlist export — save current list as M3U
7. Add album art / visualizer — ASCII art from audio

---

## Notes

- Run `uv run pytest -q` before and after changes — expect 74 passed (last run: 2026-08-30 on branch `feature/03-fix-missing-features`)
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

> History note: `feature/01-song-duration` and `feature/02-fix-design-flows` have been
> merged to `main` and pushed. `main` is the known-good baseline for the next feature branch.
