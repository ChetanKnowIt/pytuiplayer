# AI_TASK_STATE.md

## Current Branch
`feature/05-playlist-search` — active development. 102 tests pass, ruff clean, 53/53 backlog done.

## Purpose
Close **Low Priority #1** (playlist search/filter) AND **Winamp-style UI overhaul**.

## Bugs Found + Fixed

### Bug 1: Mode switch shows stale metadata
**Symptom:** Switching from radio to local mode shows "Now: ${?media-title:...} -mpv" instead of "Nothing playing"
**Root cause:** `on_radio_set_changed` cleared `current_title` but NOT `_stream_source` or `currently_playing`. The 1s `_refresh_metadata` poll kept running, saw `_stream_source=True`, read stale mpv property, and overwrote the title.
**Fix:** Added `self.currently_playing = None` and `self._stream_source = False` to the mode-switch handler.

### Bug 2: M3U search not working
**Symptom:** 2000-item M3U loads but search doesn't filter
**Root cause:** Race condition — `LocalScreen.on_mount` fires `set_timer(0.1, self._load_local)` which scans `$HOME`. When M3U is loaded, `load_m3u` populates `local_items`, but the pending timer then fires and overwrites `local_items` with `$HOME` files. Search finds nothing matching the wrong dataset.
**Fix:** 
1. Store timer reference in `self._pending_local_load`
2. Added `cancel_pending_local_load()` method
3. Call it in `on_directory_tree_file_selected` before loading M3U
4. Added fallback in `_filter_local_list` to rebuild `local_items` from ListView children if empty

## Tests
- `uv run pytest -q` → **102 passed in ~10s**
- `uv run ruff check src/` → All checks passed!
- `report_testsuite_db.py` → collected 102 / passed 102; **53/53 backlog done**

## Next Step
1. User to test mode switching and M3U search
2. If verified, WIP commit per convention
