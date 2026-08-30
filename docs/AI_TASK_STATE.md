# AI_TASK_STATE.md

## Current Branch
`feature/09-shuffle-repeat` — **Feature #4 (shuffle/repeat) implemented & green**, not yet
merged to `main`. 137 tests pass, ruff clean, 88/88 backlog done. (Feature #3 / `feature/08`
was merged to `main` earlier this session.)

## Completed This Session

### SKILL.md stale-architecture fix
`~/.hermes/skills/textual-music-player/SKILL.md` corrected (it described the pre-feature/05
monolith). AGENTS.md + live code are authoritative.

### feature/08-playback-history — Feature #3 (MERGED to main, pushed)
`HistoryTracker` controller + `H` replay binding + 15 tests. Merged `--no-ff` to `main`
(commit `03cadc5`) and pushed. main verified green (117 passed, ruff clean) before starting #4.

### feature/09-shuffle-repeat — Feature #4 (ROADMAP Low Priority #4)
Adds shuffle/repeat playback modes. Pure, deterministic navigator logic + app bindings + UI reactives.

**New / changed files:**
- `src/pytuiplayer/playlist.py` — added `import random`; `PlaylistNavigator.__init__` holds
  injectable `self._randrange`; new `_next_index(current, count, direction)` honoring
  `repeat` ("off"|"one"|"all") and `shuffle`. `_play_adjacent_local`/`_play_adjacent_radio`
  delegate to it and no-op on `None`.
- `src/pytuiplayer/tui_app.py` — `self.shuffle=False`, `self.repeat="off"` in `__init__`;
  bindings `z` → `action_toggle_shuffle`, `r` → `action_cycle_repeat`; actions update
  `NowPlaying.shuffle`/`NowPlaying.repeat` reactives + post a status message.
- `src/pytuiplayer/widgets.py` — `NowPlaying` gains `shuffle` + `repeat` reactives.
- `src/tests/test_feature_09_shuffle_repeat.py` (new, 20 tests) — `_next_index` pure logic
  (sequential/repeat-one/repeat-all/shuffle/wrap/empty), toggle/cycle actions, and
  local/radio integration with a deterministic `_randrange` injection.
- `scripts/update_testsuite_db.py` — `FILE_DESCRIPTIONS` + 20 BACKLOG rows (Low Priority #4).
- `ROADMAP.md` — added `feature/09-shuffle-repeat` section; removed #4 from unscheduled list.

**Verification:**
- `uv run pytest -q` → **137 passed** (117 prior + 20 new), 2 benign `DirectoryTree.watch_path`
  coroutine warnings.
- `uv run ruff check .` → **All checks passed!**
- `uv run python scripts/update_testsuite_db.py` → 88 backlog rows synced (88/88 done).
- `testsuite.db` report: 88/88 backlog items marked done.

**Not yet committed/merged** (user did not ask; branch `feature/09-shuffle-repeat` is local).

## Decision: Next 3 Features (user-confirmed)
Order: #3 history → #4 shuffle/repeat → #6 export. Features #3 (merged) and #4 (this branch) DONE.
Next = Feature #5 in the original ROADMAP numbering, i.e. **#6 playlist export**.

## Next Step (Feature #6 — playlist export, ROADMAP Low Priority #6)
Branch off `main` as `feature/10-playlist-export` (after merging/holding feature/09), then:
1. Add `PlaylistExporter` (or method on `playlist_loader`) that writes the current
   `local_items` (source + title + duration) to an `.m3u` file (EXTM3U/EXTINF).
2. Add `action_export_playlist()` (e.g. binding `e`) that prompts/uses a default path under the
   music dir and exports the currently-loaded list. Keep it pure/file-IO so it is unit-testable.
3. Add tests in `test_feature_10_playlist_export.py` (write to a temp file, assert EXTINF format
   and that every item is present) and mirror into `scripts/update_testsuite_db.py`.

(Deferred beyond the 3: #2 favorites, #5 configurable keys, #7 visualizer.)
