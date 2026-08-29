# ROADMAP.md — pytuiplayer

## Tech Debt & Drawbacks

### Critical Bugs

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 1 | `fetch_duration` is module-level, not a class method — `@work` decorator expects methods | `tui_app.py:41-57` | Duration fetching is broken; decorator misapplied |
| 2 | Two `max_playlist_items` assignments — second silently overwrites first | `tui_app.py:295,297` | Config intent lost; MAX_PLAYLIST_ITEMS class constant ignored |
| 3 | `_populate_missing_durations` assumes `source` is string but `load_local_files` stores Path | `tui_app.py:697` | AttributeError on Path objects |

### Design Flaws

| # | Issue | Location | Impact |
|---|-------|----------|--------|
| 4 | No Screen abstraction — mode switching via manual visibility/disabled toggling | `tui_app.py:348-390,463-518` | Brittle, repetitive, error-prone |
| 5 | `update_now_playing` dual path (post_message + direct assignment fallback) | `tui_app.py:900-926` | Confusing control flow; hard to debug |
| 6 | `item.data` shape varies: dict (M3U), dict (local), raw station dict (radio) | Throughout | Requires `isinstance` checks everywhere |
| 7 | Imports inside method bodies (`asyncio`, `Path`, `DirectoryTree`) | `tui_app.py:745-748` | Unusual, inefficient, hurts readability |
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

1. `test_fetch_duration_updates_item_data` — verify duration is stored in item.data
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

## Feature Backlog

### High Priority

1. Fix `fetch_duration` decorator — move to class method or use `@work` correctly
2. Remove duplicate `max_playlist_items` assignment — use single source of truth
3. Fix `_populate_missing_durations` Path handling — `load_local_files` stores Path, not string
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

- Run `uv run pytest -q` before and after changes — expect 26 passed
- Run `uv run ruff check .` for linting
- All tests use `FakeMPV` injection pattern — maintain this for new tests
- `PYTUIP_DEBUG=1` enables stack traces on `update_now_playing` calls
- `PYTUIP_PROFILE=1` enables performance profiling (logs to `pytuiplayer.performance`)
- `_meta_label` is set on items by `load_m3u` but NOT by `load_local_files`
- `load_stations_ui()` exists at line 882 — test at line 55 uses it correctly
