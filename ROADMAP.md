# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Design Flaws (none open)

All tracked design flaws are closed. See git history (`feature/01` through `feature/04`) for details.

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
Closes Medium Priority #1 (recursive directory scanning); remaining items below are
unscheduled follow-ups.

**Tests required to mark Done (all pass — 5 tests in `test_feature_04_medium_priority.py`):**
- ✅ `test_load_local_files_recursive` — `load_local_files` walks subdirectories (temp tree
  with nested `.mp3`s); all appear in the local list and respect `max_playlist_items` +
  batched mounting. Supporting: `test_load_local_files_recursive_respects_max_playlist_items`,
  `test_load_local_files_recursive_batched_mounting`, `test_load_local_files_top_level_still_works`.

### feature/05-playlist-search — **DONE** (branch `feature/05-playlist-search`)
Closes Low Priority #1 (playlist search/filter), Winamp-style UI overhaul, and controller architecture
refactor. The thin-orchestrator pattern from feature/01 was restored by extracting 4 controllers
into their own modules.

**New Modules:**
- `volume.py` — `VolumeController` (volume up/down/mute, widget sync)
- `metadata.py` — `MetadataPoller` (stream icy-title + local file tag polling)
- `playlist.py` — `PlaylistLoader` + `PlaylistNavigator` (M3U/local loading + prev/next)
- `tui_app.py` slimmed from 1072 → 621 lines (42% reduction)

**Winamp UI Overhaul:**
- `widgets.py` — LED-style NowPlaying (position/time/khz/kbps) with integrated seek bar (● marker)
  rendered as row 2; retro VolumeIndicator (volume bar + MUTE state)
- `screens.py` — Controls bar with prev/next buttons, search input on LocalScreen, loading status
- `musicplayer_tui.css` — Winamp retro theme: LED green (#39ff14), amber (#ffd24a) accents
- Search: `/` to focus, Escape to blur+clear, case-insensitive substring filter on loaded items

**Controller Architecture:**
- `MusicPlayerApp` routes events to controllers instead of containing business logic
- `VolumeController`, `MetadataPoller`, `PlaylistLoader`, `PlaylistNavigator` in separate modules
- Thin delegation methods in `tui_app.py` for backward compatibility with tests

**Tests required to mark Done (all pass — 20 tests in `test_feature_05_playlist_search.py`):**
- ✅ 5 search tests: substring filter, case-insensitive, clear restores, no matches, special chars
- ✅ 6 widget tests: LED display, no position, seek bar, unknown duration, volume bar, muted
- ✅ 4 layout tests: search input, loading status, prev/next buttons, focus search binding
- ✅ 5 additional tests: M3U search, mode-switch state clear, search fallback, local_items storage

**Key Bugs Fixed:**
- ListView timing: `remove_children()` + yield cycles needed before mounting new items
- Filter data vs widgets: `local_items` stores dicts, not widget references
- Mode switch clears `_stream_source` + `currently_playing` to prevent stale metadata
- M3U load cancels pending `$HOME` scan to prevent race condition
- ProgressBar shows metadata for streams (not seek bar) via `stream` reactive flag

### feature/06-fix-ui-alignment — **DONE** (branch `feature/06-fix-ui-alignment`, merged to `main`)
Compacted the layout by merging the separate `ProgressBar` widget into `NowPlaying`, creating a single
2-row Winamp-style display (LED line + seek-bar / stream-metadata line) instead of two stacked rows.

**Changes (merged):**
- `widgets.py` — Removed `ProgressBar` class; added `stream` + `meta` reactives to `NowPlaying`
- `screens.py` — Removed the separate `ProgressBar` yield from `ModeScreen.compose()`
- `tui_app.py` — `action_stop()` / `update_progress()` update `NowPlaying` (not `ProgressBar`)
- `musicplayer_tui.css` — `#now-playing` reduced from `height: 4` to a compact box; tests updated
- All tests retargeted to `NowPlaying` (no `ProgressBar` references remain)

**Status:** 102 tests pass, ruff clean, 53/53 backlog done. `main` is the known-good baseline.

> Follow-up: the `#now-playing` box still clips its 2nd row at `height: 5` (content area is only 1
> line because of border + padding). A continued UI-alignment fix (see new branch) raises the height
> to fit both rows and aligns the `#volume-indicator` inside `#controls`. See `docs/AI_TASK_STATE.md`.

### feature/08-playback-history — **DONE** (branch `feature/08-playback-history`)
Closes Low Priority #3 (playback history — track recently played items). Adds a `HistoryTracker`
controller that records every played item (radio station or local file) into an in-memory,
most-recent-first list, de-dupes consecutive repeats, and caps at `MAX_HISTORY_ITEMS` (200).

**New module:**
- `history.py` — `HistoryTracker` (`record`, `recent`, `replay`, `clear`) with `@profile` decorators.

**Integration:**
- `tui_app.py` — `self.history_tracker = HistoryTracker(self)` in `__init__`; `record()` called from
  `play_station` (radio) and both branches of `play_local` (URL stream + filesystem). New binding
  `H` (shift+h) → `action_play_history_last()` replays the most recent entry (radio via URL, local via
  `play_local`). `recent_history(n)` thin accessor for tests/UI.
- `constants.py` — `MAX_HISTORY_ITEMS = 200`.

**Tests:** 15 tests in `test_feature_08_playback_history.py` (HistoryTracker unit tests + app
integration: interleaved radio/local ordering, dedup, cap, replay, `H` binding).

**Status:** 117 tests pass (102 + 15), ruff clean, 68/68 backlog done.

### feature/09-shuffle-repeat — **DONE** (branch `feature/09-shuffle-repeat`)
Closes Low Priority #4 (shuffle/repeat modes). Adds app-level `shuffle` (bool) and
`repeat` ("off"|"one"|"all") state; `PlaylistNavigator` honors them in `play_next`/
`play_previous` via a new `_next_index()` helper (deterministic, testable).

**Changes:**
- `playlist.py` — `PlaylistNavigator._next_index(current, count, direction)`:
  - `repeat="one"` → replays current; `repeat="all"` → wraps at both ends;
    `"off"` → stops at first/last.
  - `shuffle=True` → picks a different random item (`random.randrange`, injectable
    via `self._randrange` for deterministic tests). Sequential otherwise.
  - `_play_adjacent_local` / `_play_adjacent_radio` now delegate to `_next_index`
    and no-op when it returns `None`.
- `tui_app.py` — `self.shuffle` / `self.repeat` in `__init__`; new bindings
  `z` → `action_toggle_shuffle`, `r` → `action_cycle_repeat`; actions update the
  `NowPlaying.shuffle` / `NowPlaying.repeat` reactives + post a status message.
- `widgets.py` — `NowPlaying` gains `shuffle` + `repeat` reactives.
- Tests: 20 tests in `test_feature_09_shuffle_repeat.py`.

**Status:** 137 tests pass (117 + 20), ruff clean, 88/88 backlog done.

### Low Priority (remaining — unscheduled)
2. Add station favorites — bookmark frequently played stations
5. Add configurable keybindings — user-defined bindings
6. Add playlist export — save current list as M3U
7. Add album art / visualizer — ASCII art from audio

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

> History note: `feature/01-song-duration`, `feature/02-fix-design-flows`, `feature/03-fix-missing-features`,
> and `feature/04-update-medium-priority` have been merged to `main` and pushed. `main` is the
> known-good baseline for the next feature branch.
