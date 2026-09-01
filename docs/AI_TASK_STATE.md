# AI_TASK_STATE.md

## Current Branch
`feature/12-ui-polish` (created from `main`). 156 tests pass, ruff clean.

## Completed This Session

### Architecture Review (complete)
- Read and analyzed all source modules: `tui_app.py` (now ~800 lines), `widgets.py` (216 lines),
  `screens.py` (272 lines), `playlist.py` (399 lines), `metadata.py` (109 lines), `volume.py`
  (72 lines), `history.py` (81 lines), `exporter.py` (70 lines), `mpv_player.py` (100 lines),
  `station_player.py` (39 lines), `utils.py` (48 lines), `types.py` (21 lines), constants.py (18 lines).
- Read and analyzed all 18 test files in `src/tests/` (156 tests total after adding 9 new).
- Read SKILL.md, AGENTS.md, ROADMAP.md, CSS, profiling, logging config.
- Verified baseline: `uv run ruff check .` → All checks passed!; `uv run pytest -q` → 156 passed.

### UI Review & Rating (complete)
- **Overall UI rating: 7.5/10** — solid Winamp retro aesthetic, competent implementation.
- Documented 10 areas for improvement (seek bar precision, marquee speed, no active track
  highlighting, default scan path is $HOME, volume bar too small, no button press feedback,
  no connection status, loading status placement, station index prefix redundancy,
  missing playlist total time display).
- Proposed 8 UI polish items for `feature/12-ui-polish` (below).

### feature/12-ui-polish — UI Improvements (MERGED into working tree)
All 8 planned items implemented + tested (9 new tests in `test_feature_12_ui_polish.py`):

1. **Active playback indicator in lists** — `.playing` / `.not-playing` CSS classes on
   ListItems; `play_station` and `play_local` tag the active item via `_tag_playing_item()`
   and `_tag_playing_item_for_source()`. Inactive entries dimmed to `#666`, active ones
   highlighted in `#ffd24a` (amber). Done in `tui_app.py` + `musicplayer_tui.css`.

2. **Current station marker in radio list** — same mechanism as #1; the active station
   gets the `.playing` class with amber text. Done.

3. **Faster marquee** — `NowPlaying._tick()` now advances 2 chars/tick when title > 40 chars
   (was 1 char/tick regardless). Short titles still advance 1 char/tick. Done in `widgets.py`.

4. **Loading/connection state in NowPlaying** — new `connecting` reactive on `NowPlaying`.
   `play_station` and URL-branch of `play_local` set `connecting=True`; `_refresh_stream_metadata`
   clears it when ICY metadata arrives. Render shows "⏳ Connecting..." in the stream row.
   Done in `widgets.py`, `tui_app.py`, `metadata.py`.

5. **Default local scan to ~/Music** — `LocalScreen._default_music_dir()` returns `~/Music`
   when it exists, falls back to `$HOME`. Both `compose_mode_content` and `_load_local` use it.
   Done in `screens.py`.

6. **Wider adaptive VolumeIndicator** — CSS changed from fixed `width: 25` to `width: 1fr`
   with `min-width: 25` and `max-width: 40`. Done in `musicplayer_tui.css`.

7. **Button press visual feedback** — enhanced `:focus` state (green border + bold) and
   `:hover` state (brighter background). Note: Textual doesn't support `:pressed` pseudo-class,
   so focus/hover provide the visual feedback. Done in `musicplayer_tui.css`.

8. **Playlist total time display** — `load_local_files` and `load_m3u` now compute total
   duration from known item durations and update the loading-status bar (e.g.
   "📂 Loaded 42 tracks (40 with dur — 02:15:30 total)"). Done in `playlist.py`.

### Tests Added (9 new, all passing)
- `test_default_music_dir_prefers_home_music` — ~/Music exists → returns it
- `test_default_music_dir_falls_back_to_home` — no ~/Music → returns $HOME
- `test_marquee_tick_advances_faster_for_long_titles` — 2 chars/tick for long titles
- `test_marquee_tick_resets_offset_on_new_title` — offset resets on new track
- `test_volume_indicator_renders_with_flexible_width` — render still valid
- `test_now_playing_shows_connecting_state` — "⏳ Connecting..." shown
- `test_now_playing_connecting_clears_on_meta_arrival` — metadata replaces connecting
- `test_now_playing_connecting_combines_with_stream` — connecting takes priority
- `test_load_m3u_shows_total_duration` — total duration in loading status

### Testsuite DB Updated
- Added `test_feature_12_ui_polish.py` to `FILE_DESCRIPTIONS` in `scripts/update_testsuite_db.py`.

## Architectural decisions
- Packaging path = tag a `v*` on `main` (let `build.yml` build + publish). Never hand-build.
- Release cadence = 3 merged features → MINOR bump + tag. Ledger in `docs/RELEASE_CADENCE.md`.
- `mpv` independent of the package (confirmed scope decision).
- Architecture is well-structured: thin orchestrator + 6 focused controller modules.
- Textual CSS doesn't support `:pressed` — used `:focus` + `:hover` for button feedback.
- `brightness` is not a valid Textual CSS property — removed from button hover.

## Next Step
Create `feature/13-audio-visualizer` branch and implement the visualizer:
- New `visualizer.py` module with `AudioVisualizer` controller
- NowPlaying gains `v` keybinding to cycle modes (Off → Waveform → Spectrum → VU Meter)
- Polls mpv for audio samples, renders ASCII art
- Tests with mock audio data

After that: feature/15 (configurable keybindings), then feature/14 (station favorites).

Remaining ROADMAP Low Priority items (reordered):
- **Next:** feature/13-audio-visualizer (audio visualization)
- **Later:** #5 configurable keybindings, #2 station favorites
