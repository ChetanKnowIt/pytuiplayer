# AI_TASK_STATE.md

## Current Branch
feature/01-song-duration (ahead 1 commit from origin, plus uncommitted local changes)

## Completed
- Fixed test FakeList.mount() to accept *items (batch API) - test_tui_app.py, 483 lines
- Fixed ruff E501 line-length violations - logging_config.py, station_player.py
- Excluded tui_app_ast.pyi and tests from ruff E501 - pyproject.toml, 40 lines
- All 26 tests passing (was 24 passed, 2 failed)
- ruff check: All checks passed
- Added logging_config.py with setup_logging() and get_logger() - proper logging infrastructure
- Added profiling.py with @profile and @profile_async decorators
- Applied profiling decorators to ~30 critical UI methods and event handlers
- Added PYTUIP_PROFILE=1 env var control for performance profiling

## Profiling Applied To
- NowPlaying._tick (0.6s marquee interval)
- NowPlaying.on_now_playing_message (title update messages)
- NowPlaying.render (renders now playing display)
- ProgressBar.render (renders progress bar)
- VolumeIndicator.render (renders volume display)
- update_volume_ui (called on every volume change)
- _refresh_metadata (1.0s radio metadata poll)
- action_play_playlist (playlist playback)
- load_stations (JSON file loading)
- load_stations_ui (station list population)
- _load_json (async file I/O)
- on_mount, on_radio_set_changed, load_local_files, load_m3u
- on_button_pressed, on_list_view_selected, on_directory_tree_file_selected
- action_volume_up, action_volume_down, action_toggle_mute
- action_toggle_play, action_play, action_pause, action_stop
- action_seek_forward, action_seek_backward
- update_now_playing, update_progress

## Tests
- 26 passed in 0.59s
- ruff check: All checks passed

## Remaining
- Decide on next task: fix duplicate max_playlist_items (line 295/297), fix module-level fetch_duration, or other

## Architectural Decisions
- Tests use FakeList with *items signature to match Textual's batch mount API
- .pyi stub excluded from linting (documentation only)
- Tests excluded from E501 (long test strings)
- Profiling is opt-in via PYTUIP_PROFILE=1 env var (no overhead when disabled)
- Profiling logs at DEBUG level to pytuiplayer.performance logger

## Next Step
Awaiting task assignment from user. Options:
1. Fix duplicate max_playlist_items assignment in __init__ (line 295/297)
2. Convert module-level fetch_duration to a proper class method
3. Refactor monolithic tui_app.py
4. Add recursive directory scanning for load_local_files
