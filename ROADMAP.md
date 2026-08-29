# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Critical Bugs

| # | Issue | Location | Impact | Status |
|---|-------|----------|--------|--------|
| 1 | `fetch_duration` is module-level, not a class method — `@work` decorator expects methods | `tui_app.py:41-57` (was) | Was broken; now a proper `async` `@work`-spawned class method (`run_worker`) | ✅ Fixed |
| 2 | Two `max_playlist_items` assignments — second silently overwrites first | `tui_app.py:295,297` (was) | Was overwriting class constant; now single source of truth | ✅ Fixed |
| 3 | `_populate_missing_durations` assumes `source` is string but `load_local_files` stores Path | `tui_app.py:697` (was) | AttributeError on Path; now handles Path/`title`/`meta` | ✅ Fixed |

### Design Flaws

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 4 | No Screen abstraction — mode switching via manual visibility/disabled toggling | `tui_app.py:348-390,463-518` | Brittle, repetitive, error-prone |
| 5 | `update_now_playing` dual path (post_message + direct assignment fallback) | `tui_app.py:900-926` | Confusing control flow; hard to debug |
| 6 | `item.data` shape varies: dict (M3U), dict (local), raw station dict (radio) | Throughout | Requires `isinstance` checks everywhere |
| 7 | Imports inside method bodies (`asyncio`, `Path`, `DirectoryTree`) | `tui_app.py:745-748` (was) | Was unusual/inefficient; ✅ Fixed — hoisted to module top | ✅ Fixed |
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

## Infrastructure (Completed)

| # | Item | Status |
|---|------|--------|
| 1 | Logging module (`logging_config.py`) with `setup_logging()` and `get_logger()` | Done |
| 2 | Profiling decorators (`@profile`, `@profile_async`) in `profiling.py` | Done |
| 3 | Profiling applied to all critical UI event handlers and render methods | Done |
| 4 | `PYTUIP_PROFILE=1` env var control for performance profiling | Done |
| 5 | `PYTUIP_LOG_LEVEL` env var control for log level | Done |

---

## Test Backlog

### Missing Unit Tests

1. `test_fetch_duration_updates_item_data` — verify duration is stored in item.data ✅ Done
2. `test_on_button_pressed_play_pause_stop` — verify button handlers call mpv correctly
3. `test_on_list_view_selected_station_mode` — verify station selection triggers play_station
4. `test_on_list_view_selected_local_mode` — verify local selection triggers play_local
5. `test_action_seek_forward_backward` — verify seek calls mpv.seek with correct delta
6. `test_action_seek_to_percent_no_absolute_fallback` — verify relative fallback works
7. `test_update_progress_sets_bar_values` — verify progress/duration are set on bar
8. `test_refresh_metadata_updates_title_for_radio` — verify ICY title updates current_title
9. `test_refresh_metadata_noop_for_local_mode` — verify no metadata polling in local mode
10. `test_play_local_url_bypasses_file_checks` — verify URL handling path
11. `test_play_local_failure_shows_error` — verify error toast on play failure
12. `test_load_m3u_respects_max_playlist_items` — verify truncation (partial coverage exists)
13. `test_load_m3u_handles_aiofiles_and_sync_fallback` — verify both code paths
14. `test_directory_tree_json_in_radio_mode` — verify station file loading
15. `test_directory_tree_unsupported_file_shows_error` — verify error notification
16. `test_volume_up_clamps_at_100` — verify volume ceiling
17. `test_volume_down_clamps_at_0_and_mutes` — verify mute on zero
18. `test_mute_restores_previous_volume` — verify _prev_volume logic
19. `test_now_playing_marquee_scrolls_long_titles` — verify marquee offset logic
20. `test_progressbar_render_with_meta_no_duration` — verify radio metadata display

### Integration / Widget Tests

1. `test_now_playing_widget_renders_countdown` — verify remaining time display
2. `test_volume_indicator_shows_muted_state` — verify mute icon
3. `test_mode_switch_stops_playback` — verify mpv.stop() on mode change
4. `test_mode_switch_updates_visibility` — verify all three widgets toggled

---

## Test Inventory (existing suite)

> Run with `uv run pytest -q` from the repo root. Network tests are marked `network`
> and skip automatically when no live stream is reachable.

### `src/tests/test_main_entry.py` (1)
| Test | Description |
|------|-------------|
| `test_main_calls_run` | Verifies `__main__.main()` constructs the app and calls `.run()` (returns 0). |

### `src/tests/test_app_integration.py` (1)
| Test | Description |
|------|-------------|
| `test_app_shows_nowplaying_during_play_and_progress` | End-to-end: playlist play sets mpv source + title, and progress updates flow to NowPlaying/ProgressBar widgets. |

### `src/tests/test_station_player.py` (3)
| Test | Description |
|------|-------------|
| `test_stationplayer_play_uses_mpv` | StationPlayer.play(index) forwards the correct URL to the injected mpv. |
| `test_stationplayer_update_stations_reads_file` | update_stations() reloads from a JSON file and keeps previous on missing file. |
| `test_update_stations_with_invalid_json_keeps_previous` | Invalid JSON returns False and leaves stations unchanged. |

### `src/tests/test_now_playing_widget.py` (2)
| Test | Description |
|------|-------------|
| `test_now_playing_message_updates_widget` | NowPlayingMessage updates title/source/state and renders the title. |
| `test_now_playing_marquee_rotates_and_has_fixed_width` | Marquee returns fixed-width slices and rotates offset on tick. |

### `src/tests/test_mpv_player.py` (2)
| Test | Description |
|------|-------------|
| `test_mpvplayer_play_pause_stop_and_volume` | MPVPlayer wrapper drives play/pause/stop/volume on the injected backend. |
| `test_mpvplayer_seek_and_time_duration` | get_time_pos/get_duration/seek delegate correctly to the backend. |

### `src/tests/test_tui_app.py` (21)
| Test | Description |
|------|-------------|
| `test_tui_toggle_play_and_stop` | toggle_play swaps pause/unpause; stop resets title and progress/duration. |
| `test_load_stations_ui_updates_list` | load_stations_ui() mounts one ListItem per station with raw dict data. |
| `test_progressbar_unknown_duration` | ProgressBar renders "Duration unknown" when progress/duration are 0. |
| `test_progressbar_formats_mmss_and_shows_bar` | ProgressBar formats `MM:SS / MM:SS` inside a bracketed bar. |
| `test_seek_to_percent_uses_absolute_if_available` | seek_to_50 uses absolute seek when duration is known. |
| `test_seek_to_percent_no_duration_is_noop` | seek_to_50 is a no-op (no crash) when duration is unknown. |
| `test_volume_up_down_and_mute` | Volume steps by 5; mute sets 0 and unmute restores prior volume. |
| `test_explicit_play_and_pause` | action_play/action_pause map to unpause/pause on the backend. |
| `test_visibility_toggle_hides_unused_widgets` | Radio/local mode switch toggles visibility of station/local/tree widgets. |
| `test_progressbar_shows_radio_meta_when_streaming` | ProgressBar shows ICY metadata in `meta` while radio streaming. |
| `test_play_local_calls_mpv_and_sets_title` | play_local() plays the path and sets title to the filename stem. |
| `test_directory_tree_selection_plays_file_when_local` | DirectoryTree file selection in local mode plays the chosen file. |
| `test_play_local_uses_mutagen_tags_if_available` | play_local() prefers `Album - Title` from mutagen tags when present. |
| `test_load_m3u_parses_and_populates` | load_m3u parses #EXTINF, populates dict data, and sets `_meta_label`. |
| `test_load_large_m3u_is_truncated_and_batched` | load_m3u truncates to max_playlist_items and yields to the loop per batch. |
| `test_playlist_item_uses_extinf_metadata_on_play` | Selecting an M3U item plays its source and shows EXTINF metadata as title. |
| `test_play_playlist_starts_first_item` | action_play_playlist plays the first list item and sets its title. |
| `test_fetch_duration_method_updates_item_data` | fetch_duration reads tag, stores duration, and refreshes the item label. |
| `test_load_local_files_does_not_call_bool_flag` | Regression: load_local_files spawns the worker (not a bool flag) per item. |
| `test_populate_missing_durations_handles_local_path_source` | Regression: _populate_missing_durations handles Path source + title-only data. |
| `test_max_playlist_items_single_source_of_truth` | Regression: max_playlist_items equals the MAX_PLAYLIST_ITEMS class constant (2000). |

### `src/tests/test_radio_integration.py` (1) — marked `network`
| Test | Description |
|------|-------------|
| `test_radio_starts_stream_and_updates_now_playing` | Runs the real TUI headless, starts a reachable station, asserts mpv connects and `currently_playing == "radio"`; skips offline. |

**Total: 31 test functions across 7 files** (the `network`-marked radio test passes when a live stream is reachable and auto-skips offline).

---

## Feature Backlog

### High Priority

1. Fix `fetch_duration` decorator — move to class method or use `@work` correctly ✅ Done
2. Remove duplicate `max_playlist_items` assignment — use single source of truth ✅ Done
3. Fix `_populate_missing_durations` Path handling — `load_local_files` stores Path, not string ✅ Done
4. Extract imports to module top — move `asyncio`, `Path`, `DirectoryTree` imports

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

- Run `uv run pytest -q` before and after changes — expect 31 passed (last run: 2026-08-29 23:29 IST)
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
