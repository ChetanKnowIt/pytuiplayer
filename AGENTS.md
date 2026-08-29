# AGENTS.md — pytuiplayer

## Project Overview

Terminal-based music player built with Python 3.12, Textual (TUI framework), and mpv. Supports two playback modes:
- **Radio mode**: Internet radio streams from a JSON station list
- **Local mode**: Local MP3 files and M3U playlists

## Key Files

| File | Role |
|------|------|
| `src/pytuiplayer/tui_app.py` | Main App + all widgets + business logic (1186-line monolith) |
| `src/pytuiplayer/mpv_player.py` | Thin wrapper around `python-mpv` |
| `src/pytuiplayer/station_player.py` | Station list manager |
| `src/pytuiplayer/stations.json` | Default radio stations |
| `src/pytuiplayer/musicplayer_tui.css` | Textual CSS theme |
| `src/pytuiplayer/__main__.py` | CLI entrypoint |
| `src/tests/` | Pytest test suite |

## Architecture

### Textual App

Single `MusicPlayerApp(App)` class in `tui_app.py`. No Screen abstraction — mode switching is done via widget visibility toggling (`display`, `visible`, `disabled`).

### Widgets (all defined in tui_app.py)

| Widget | Type | Location |
|--------|------|----------|
| `NowPlaying(Static)` | Reactive | `tui_app.py:95` |
| `ProgressBar(Static)` | Reactive | `tui_app.py:211` |
| `VolumeIndicator(Static)` | Reactive | `tui_app.py:247` |

### State Management

- **Reactive state**: Textual `reactive` descriptor on widget attributes (`title`, `state`, `source`, `progress`, `duration`, `volume`, `muted`, `_offset`)
- **App-level state**: Plain attributes on `MusicPlayerApp` (`volume`, `muted`, `current_title`, `option_mode`, `currently_playing`, `_prev_volume`)
- **Message pattern**: `NowPlayingMessage(Message)` posted from `update_now_playing()` to `NowPlaying` widget; handler `on_now_playing_message` updates widget fields

### Event Flow

- `on_mount()`: Loads stations JSON, initializes volume, sets up polling intervals
- `on_radio_set_changed()`: Mode switching (radio ↔ local) with visibility toggling
- `on_button_pressed()`: Play/Pause/Stop button handlers
- `on_list_view_selected()`: Station/local list selection
- `on_directory_tree_file_selected()`: File browser selection (JSON/M3U/MP3)
- Polling: `update_progress()` (0.5s), `_refresh_metadata()` (1.0s)
- Marquee: `NowPlaying._tick()` (0.6s interval)

### CSS

Single file: `musicplayer_tui.css`. Dark theme (`#0b0b0b` background, `#f0e6c8` text) with orange (#ff9e00) accents and green (#39ff14) progress bar. Uses Textual CSS selectors (`#id`, `Widget:disabled`, `ListItem.-selected`).

### Keyboard Bindings

| Key | Action |
|-----|--------|
| `q` | Quit |
| `space` | Toggle play/pause |
| `p` | Play |
| `k` | Pause |
| `s` | Stop |
| `h` / `l` | Seek -5s / +5s |
| `1` / `5` / `9` | Seek to 10% / 50% / 90% |
| `+` / `-` | Volume up / down |
| `m` | Toggle mute |

### Audio Architecture

- `MPVPlayer`: Wraps `python-mpv` (`mpv.MPV`). Supports DI via `player=` or `player_factory=` constructor args. Defensive `hasattr` checks for seek/duration across binding versions.
- `StationPlayer`: Holds `[{"name":..., "url":...}]` list, `play(index)` delegates to `MPVPlayer.play(url)`.
- Metadata polling via `_refresh_metadata()` (ICY/media-title from mpv properties).

### Library/Database

No database. File-based:
- Radio: JSON station files (`stations.json`), loaded via `anyio.open_file` async I/O
- Local: `load_local_files()` iterates directory for `.mp3`, creates `ListItem` with `item.data = {"source": Path, "title": str, "duration": None}`
- M3U: `load_m3u()` parses `#EXTINF` metadata, resolves relative paths, batched mounting (200/batch, max 5000)

### Duration Fetching

- `fetch_duration`: `@work(thread=True, exclusive=True)` function at module level (NOT a class method — likely broken since `@work` expects methods)
- `_populate_missing_durations`: Optional async background task (disabled by default via `self.fetch_duration = False`)

## Testing

- Framework: pytest
- Config: `pytest.ini` (`testpaths = src/tests`)
- Excluded: Legacy manual scripts in `src/` (`test_mpv.py`, `test_pyradio.py`, `test_raw_mpv.py`, `test_main.py`)
- Pattern: Inject `FakeMPV` / `FakeMPVPlayer` via `app.mpv = ...`
- Stub `app.query_one` and `app.update_now_playing` to avoid Textual DOM
- Use `asyncio.run()` for async methods
- Run: `uv run pytest -q` from repo root (expects 26 passed)

## Linting/Formatting

Ruff configured in `pyproject.toml`:
- Line length: 100
- Target: py312
- Rules: E, F, I, UP, B
- Fix on save enabled

## Debugging

Set `PYTUIP_DEBUG=1` environment variable for debug tracing (stack traces on `update_now_playing` calls, error logging in `on_now_playing_message`).

## Common Pitfalls

1. **`fetch_duration` is module-level**, not a class method. The `@work` decorator expects methods — this is likely broken.
2. **Two `max_playlist_items` assignments** in `__init__` (lines 291, 293) — the second silently overwrites the first.
3. **Silent exception swallowing**: Most methods have bare `try/except: pass` — intentional to keep TUI alive, but makes debugging hard.
4. **No Screen abstraction**: Mode switching via manual visibility toggling, not Textual's Screen stack.
5. **`update_now_playing` dual path**: Posts a message AND has direct-assignment fallback — both must work.
6. **Test asserts `_meta_label`** (test_tui_app.py:378) but production code never sets it — this test will fail.
7. **`item.data` shape varies**: Can be a dict (`load_m3u`), a dict (`load_local_files`), or a raw station dict — always use `isinstance` checks.

## Rules for Modifying Existing Components

1. Always inject `FakeMPV` in tests — never use real mpv in unit tests.
2. Stub `app.query_one` and `app.update_now_playing` to avoid Textual DOM dependencies.
3. Keep the defensive `try/except` pattern for UI updates (prevents TUI crashes).
4. Maintain backward compatibility for `item.data` shapes (dict vs Path/str).
5. Test both radio and local mode paths.
6. Run `uv run pytest -q` and `uv run ruff check .` before finishing.

## Rules for Adding New Components

1. Add widgets to `tui_app.py` (no separate widget module currently exists).
2. Use `reactive` for widget state that triggers re-render.
3. Use `Message` subclasses for cross-widget communication.
4. Add corresponding keyboard bindings to `BINDINGS` list.
5. Add tests in `src/tests/` following the `FakeMPV` injection pattern.
6. Update CSS in `musicplayer_tui.css` for new widget IDs.
