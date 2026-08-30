# AI_TASK_STATE.md

## Current Branch
`feature/08-playback-history` — **feature #3 (playback history) implemented & green**, not yet
merged to `main`. 117 tests pass, ruff clean, 68/68 backlog done.

## Completed This Session

### SKILL.md stale-architecture fix (pre-feature work)
- `~/.hermes/skills/textual-music-player/SKILL.md` still described `tui_app.py` as a ~897-line
  monolith. Corrected §Architecture (now "thin orchestrator ~621 lines") and both Procedure
  sections (new components go in `widgets.py`/`screens.py`, not `tui_app.py`). AGENTS.md + live
  code remain authoritative.

### feature/08-playback-history — Feature #3 (ROADMAP Low Priority #3)
Adds a playback-history tracker. Pure, DOM-free controller + thin app integration + replay binding.

**New / changed files:**
- `src/pytuiplayer/history.py` (new, 92 lines) — `HistoryTracker` (`record`, `recent`, `replay`,
  `clear`, `count`). Bounded `collections.deque(maxlen=MAX_HISTORY_ITEMS)`, most-recent-first,
  dedupes consecutive repeats, ignores empty title/source. `@profile` on each method.
- `src/pytuiplayer/constants.py` — added `MAX_HISTORY_ITEMS = 200`.
- `src/pytuiplayer/tui_app.py`:
  - import `HistoryTracker`; instantiate `self.history_tracker` in `__init__`.
  - `play_station` records `("radio", name, url)`.
  - `play_local` records in BOTH branches (URL stream + filesystem), using `source_path or source_str`.
  - New binding `H` (shift+h) → `action_play_history_last()` (replays most-recent entry).
  - `recent_history(n)` thin accessor for tests/UI.
- `src/tests/test_feature_08_playback_history.py` (new, 15 tests) — tracker unit tests +
  app integration (interleaved ordering, dedup, cap, replay, `H` binding, no-history warning).
- `scripts/update_testsuite_db.py` — `FILE_DESCRIPTIONS` + 15 BACKLOG rows (Low Priority #3).
- `ROADMAP.md` — added `feature/08-playback-history` section; removed #3 from unscheduled list.

**Verification:**
- `uv run pytest -q` → **117 passed** (102 prior + 15 new), 2 benign `DirectoryTree.watch_path`
  coroutine warnings.
- `uv run ruff check .` → **All checks passed!**
- `uv run python scripts/update_testsuite_db.py` → 68 backlog rows synced (68/68 done).
- `testsuite.db` report: 68/68 backlog items marked done.

**Not yet committed** (user did not ask to commit; branch `feature/08-playback-history` is local,
unmerged). No merge performed.

## Architecture Review (recorded earlier this session)
- Thin-orchestrator architecture confirmed: `tui_app.py` (621 lines) delegates to controllers
  `volume.py` / `metadata.py` / `playlist.py` / `station_player.py` / (new) `history.py`.
- State model, event flow, and single-update-path (`NowPlayingMessage`) all verified by tracing
  handlers — documented in the prior AI_TASK_STATE revision. No architectural regressions.

## Decision: Next 3 Features (user-confirmed)
Order: **#3 history → #4 shuffle/repeat → #6 export** (from ROADMAP Low Priority #2–#7).
Feature #3 (this branch) is DONE. Next = Feature #4.

## Next Step (Feature #4 — shuffle/repeat modes, ROADMAP Low Priority #4)
Branch off `main` as `feature/09-shuffle-repeat` (after merging/holding feature/08), then:
1. Add `shuffle: bool` + `repeat` enum (`"off"|"one"|"all"`) to `MusicPlayerApp.__init__`.
2. Extend `PlaylistNavigator` (`play_previous`/`play_next`) to honor shuffle (random next item) and
   repeat (`one` = same index again; `all` = wrap to 0 at end). Keep `_resolve_playlist_items`.
3. Add bindings (e.g. `z` shuffle toggle, `r` repeat cycle) and a small indicator in `NowPlaying`
   reactives (`shuffle`, `repeat`) so the render reflects state. Add tests in
   `test_feature_09_shuffle_repeat.py` and mirror into `scripts/update_testsuite_db.py`.

(Deferred beyond the 3: #2 favorites, #5 configurable keys, #7 visualizer.)
