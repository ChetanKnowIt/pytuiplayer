# AI_TASK_STATE.md

## Current Branch
feature/01-song-duration (ahead 2 commits from origin, plus uncommitted local changes)

## Completed This Session
### Song-duration subsystem bug fixes (ROADMAP critical bugs #1-3 / High Priority #1-3)
- Converted module-level `@work`-decorated `fetch_duration` function (tui_app.py:44-61, was broken) into a proper `async def fetch_duration(self, item)` class method. `load_local_files` now spawns it via `self.run_worker(self.fetch_duration, item)` — the canonical, correctly-applied Textual worker pattern. (tui_app.py)
- Fixed `fetch_duration` name collision: old `self.fetch_duration = False` boolean flag collided with the worker call `self.fetch_duration(file)` -> `TypeError: 'bool' object is not callable` at runtime in `load_local_files`. Replaced flag with `self.fetch_duration_eager` (default False). (tui_app.py:303)
- Removed duplicate `max_playlist_items` assignment in `__init__` (was set to MAX_PLAYLIST_ITEMS=2000 then silently overwritten by 5000). Now a single assignment from the `MAX_PLAYLIST_ITEMS` class constant. (tui_app.py:300-302)
- Rewrote `_populate_missing_durations` (tui_app.py) to handle a `source` that is a `Path` (or string) and a `data` dict carrying only `title` (no `meta`), as produced by `load_local_files`. Old code called `str.startswith` on a `Path` and indexed `item.data['meta']` (KeyError). Now uses `isinstance`/`Path(src)` and falls back `meta or title or filename`. Also skips non-existent files and radio URLs safely.

### Tests added (src/tests/test_tui_app.py, +115 lines)
- `test_fetch_duration_method_updates_item_data` — verifies duration stored in item.data and label updated (02:17 for 137s).
- `test_load_local_files_does_not_call_bool_flag` — regression guard: load_local_files calls the worker method, not a bool flag (would have raised 'bool is not callable').
- `test_populate_missing_durations_handles_local_path_source` — regression: handles Path source + title-only dict.
- `test_max_playlist_items_single_source_of_truth` — regression: max_playlist_items == 2000 from class constant.

### Docs updated
- ROADMAP.md: marked critical bugs #1-3 and High-Priority #1-3 as ✅ Done; marked test #1 done.
- AGENTS.md: updated pitfall #1 (`fetch_duration` now a class method + `fetch_duration_eager` flag) and #2 (duplicate assignment fixed).

## Tests
- 30 passed in 0.64s (was 26; +4 new regression tests)
- ruff check: All checks passed

## Remaining (suggested next tasks, not started)
- Extract imports to module top (ROADMAP #4 / Design Flaw #7): `asyncio`, `Path`, `DirectoryTree` imported inside method bodies.
- Add recursive directory scanning for load_local_files (ROADMAP Medium #1).
- Add a keyboard binding for `action_play_playlist` (ROADMAP #13).
- Initialize git integration / commit when requested by user.

## Architectural Decisions
- `fetch_duration` is a plain `async def` method (NOT `@work`-decorated directly) so it is unit-testable via `asyncio.run(app.fetch_duration(item))`; it is launched in the UI via `self.run_worker(...)` which IS the correct Textual worker entry point.
- `fetch_duration_eager` (bool) gating `_populate_missing_durations` at M3U load time is the replacement for the old `fetch_duration` bool flag.
- Backward-compat `item.data` shapes preserved: local = {source(Path), title, duration}; m3u = {source, meta, duration}. `_populate_missing_durations` now tolerates both.
- Tests stub `app.call_from_thread`/`query_one` and patch `pytuiplayer.tui_app.MutagenFile` (module-level binding) to avoid real mutagen/file I/O.

## Next Step
Awaiting task assignment from user. Suggested: extract in-method imports to module top, OR add recursive dir scan, OR add playlist keyboard binding. (Do NOT commit unless explicitly asked.)
