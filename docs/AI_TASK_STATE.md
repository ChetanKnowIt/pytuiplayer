# AI_TASK_STATE.md

## Current Branch
`feature/02-fix-design-flows` (branched off `main` @ `dcfeadf`, known-good baseline: 53 tests, ruff clean)

## Purpose
Structural debt refactor: Screen abstraction, single now-playing update path, unified `item.data` shape, structured error handling, responsive progress bar, and a code split (widgets/handlers/loaders → modules).

## Completed This Session

### A. Foundation modules (no behavior change)
- `src/pytuiplayer/constants.py` — `MAX_PLAYLIST_ITEMS`, `DEFAULT_PLAYLIST_BATCH_SIZE`, `ICON_OK`, `ICON_ERR`
- `src/pytuiplayer/utils.py` — `parse_extinf`, `resolve_source`, `fmt_mmss` (pure functions)
- `src/pytuiplayer/types.py` — `ItemData` TypedDict (unified shape for `ListItem.data`)

### B. Behavior-preserving improvements
- `src/pytuiplayer/widgets.py` — `NowPlaying`, `NowPlayingMessage`, `ProgressBar`, `VolumeIndicator`
  - `ProgressBar.render()` derives bar width from `self.size.width` (minus padding), clamped to [20, 160] — no longer hardcoded 160
- `src/pytuiplayer/tui_app.py`:
  - `update_now_playing` now posts `NowPlayingMessage` only — direct-assignment fallback removed (single path)
  - Bare `except: pass` replaced with `logger.debug`/`logger.warning`/`logger.exception` (structured logging)
  - `play_local` reads both `path.get("meta")` and `path.get("title")` for unified `item.data`
  - `action_stop`, `update_progress`, `play_station` made defensive for headless/screen-less contexts

### C. Screen abstraction
- `src/pytuiplayer/screens.py` — `ModeScreen` base class + `RadioScreen` / `LocalScreen` subclasses
  - Mode switching via `self.switch_screen(...)` instead of manual visibility/disabled toggling
  - Each screen composes shared widgets (Header, Footer, NowPlaying, ProgressBar, controls) + mode-specific content
  - `on_mount` loads stations/local files via `set_timer(0.1, ...)` after widgets are ready

### D. Acceptance tests
- `src/tests/test_feature_02_design_flows.py` — 6 new tests (all pass):
  - `test_radio_local_use_screens_not_visibility_toggle`
  - `test_update_now_playing_single_path`
  - `test_item_data_unified_typeddict`
  - `test_no_silent_exceptions`
  - `test_progressbar_uses_widget_width`
  - `test_code_split_regression`
- Updated `test_backlog_coverage.py::test_mode_switch_updates_visibility` to verify screen-switch behavior
- Updated `test_tui_app.py::test_visibility_toggle_hides_unused_widgets` to verify screen-switch behavior

### E. Backward compatibility
- `MusicPlayerApp.MAX_PLAYLIST_ITEMS` class constant retained (aliased to imported value) so existing tests still pass
- `on_radio_set_changed` wraps screen-switch logic in try/except so unit tests without a screen stack still work
- `action_stop`/`update_progress`/`play_station` made defensive for headless/screen-less contexts

## Tests
- `uv run pytest -q` → **59 passed in ~9s** (53 original + 6 new acceptance tests)
- `uv run ruff check .` → All checks passed

## Remaining
- None for this branch. All 6 acceptance tests pass; original 53 tests still pass.
- Awaiting user decision on merging `feature/02-fix-design-flows` into `main`.

## Architectural Decisions
- `constants.py` / `utils.py` / `types.py` are pure (no Textual/mpv imports) for reusability
- `widgets.py` groups all three shared widgets (no separate package to keep imports simple)
- `screens.py` uses a base `ModeScreen` class to avoid duplicating the shared widget composition
- `on_mount` uses `push_screen(RadioScreen())` directly (not deferred) — headless `run_test()` works because the screen stack is ready by then
- `RadioScreen.on_mount` / `LocalScreen.on_mount` use `set_timer(0.1, ...)` to load data after widgets mount
- `update_now_playing` uses a single message-posting path; `on_now_playing_message` is the sole handler
- `ProgressBar` derives bar width from widget size with MIN/MAX clamps for readability
- Screen-switch logic in `on_radio_set_changed` is wrapped in try/except for test compatibility

## Next Step
Branch complete. Next feature should start on a fresh branch off updated `main`
(`git checkout main && git pull && git checkout -b feature/<next-slug>`), using the
DB-tracked Test Backlog as the prerequisite checklist.
