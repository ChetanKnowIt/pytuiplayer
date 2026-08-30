# AGENTS.md — pytuiplayer

## Project Overview

Terminal-based music player built with Python 3.12, Textual (TUI framework), and mpv. Supports two playback modes:
- **Radio mode**: Internet radio streams from a JSON station list
- **Local mode**: Local MP3 files and M3U playlists

## Key Files

| File | Role |
|------|------|
| `src/pytuiplayer/tui_app.py` | Main App + business logic (thin orchestrator) |
| `src/pytuiplayer/widgets.py` | NowPlaying, ProgressBar, VolumeIndicator widgets |
| `src/pytuiplayer/screens.py` | ModeScreen, RadioScreen, LocalScreen |
| `src/pytuiplayer/constants.py` | MAX_PLAYLIST_ITEMS, ICON_OK, ICON_ERR |
| `src/pytuiplayer/utils.py` | Pure helpers: parse_extinf, resolve_source, fmt_mmss |
| `src/pytuiplayer/types.py` | ItemData TypedDict |
| `src/pytuiplayer/mpv_player.py` | Thin wrapper around `python-mpv` |
| `src/pytuiplayer/station_player.py` | Station list manager |
| `src/pytuiplayer/stations.json` | Default radio stations |
| `src/pytuiplayer/musicplayer_tui.css` | Textual CSS theme |
| `src/pytuiplayer/logging_config.py` | Logging configuration (setup_logging, get_logger) |
| `src/pytuiplayer/profiling.py` | Performance profiling decorators (@profile, @profile_async) |
| `src/pytuiplayer/__main__.py` | CLI entrypoint |
| `src/tests/` | Pytest test suite |
| `src/tests/testsuite_db.py` | SQLite test-inventory DB helpers (schema + idempotent upserts) |
| `src/tests/test_backlog_coverage.py` | ROADMAP Test Backlog coverage (22 tests) |
| `src/tests/test_feature_02_design_flows.py` | feature/02 acceptance tests (6 tests) |
| `scripts/` | Dev scripts and manual test scripts |
| `scripts/update_testsuite_db.py` | Rebuild/enrich `testsuite.db` (files + backlog mirror) |
| `scripts/report_testsuite_db.py` | Print the test inventory / backlog / runs |
| `pytuiplayer.spec` | PyInstaller build spec |

## Architecture

### Textual App

`MusicPlayerApp(App)` in `tui_app.py` is a thin orchestrator. Widgets live in `widgets.py`, screens in `screens.py`, constants in `constants.py`, helpers in `utils.py`, and types in `types.py`.

### Screen Abstraction

Mode switching uses Textual's screen stack (`RadioScreen` / `LocalScreen` in `screens.py`), not manual visibility toggling. `MusicPlayerApp.query_one` delegates to the active screen so widgets inside pushed screens are found.

```
MusicPlayerApp
  └─ push_screen(RadioScreen)   # radio mode
  └─ push_screen(LocalScreen)   # local mode
```

Each screen composes shared widgets (Header, Footer, NowPlaying, ProgressBar, controls) plus mode-specific content.

### Widgets (in widgets.py)

| Widget | Type | Purpose |
|--------|------|---------|
| `NowPlaying(Static)` | Reactive | Title, source, countdown, marquee scrolling |
| `ProgressBar(Static)` | Reactive | Progress bar (responsive width), elapsed/total, radio metadata |
| `VolumeIndicator(Static)` | Reactive | Volume/mute display |

### State Management

- **Reactive widget state**: Textual `reactive` descriptor on widget attributes (`title`, `state`, `progress`, `duration`, `volume`, `muted`, `_offset`)
- **App-level state**: Plain attributes on `MusicPlayerApp` (`volume`, `muted`, `current_title`, `option_mode`, `currently_playing`, `_prev_volume`)
- **Message pattern**: `NowPlayingMessage(Message)` posted from `update_now_playing()` to `NowPlaying` widget; handler `on_now_playing_message` updates widget fields (single path — no direct-assignment fallback)

### Event Flow

- `on_mount()`: Initializes volume, sets up polling intervals, pushes `RadioScreen`
- `on_radio_set_changed()`: Mode switching via `switch_screen(RadioScreen)` / `switch_screen(LocalScreen)`
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

No runtime database — the app is file-based:
- Radio: JSON station files (`stations.json`), loaded via `anyio.open_file` async I/O
- Local: `load_local_files()` iterates directory for `.mp3`, creates `ListItem` with `item.data = {"source": Path, "title": str, "duration": None}`
- M3U: `load_m3u()` parses `#EXTINF` metadata, resolves relative paths, batched mounting (200/batch, max 2000 via `MAX_PLAYLIST_ITEMS`)

Note: the test suite maintains a *generated* SQLite inventory at the repo root
(`testsuite.db`) for tracking tests/backlog/runs. It is gitignored and refreshed on
every `uv run pytest` run (see `src/tests/testsuite_db.py`). It is not app data.

### Duration Fetching

- `fetch_duration(self, item)`: a plain `async def` class method that reads the file tag
  via the module-level `MutagenFile` binding, stores `item.data["duration"]`, and refreshes
  the item's label. It is launched off the main thread from `load_local_files` via
  `self.run_worker(self.fetch_duration, item)`.
- `_populate_missing_durations(list_view)`: optional async background task that fills missing
  durations for already-mounted items. It handles Path/string/URL sources (skips URLs and
  non-existent files) and is enabled only when `self.fetch_duration_eager` is `True`.

## Testing

- Framework: pytest
- Config: `pytest.ini` (`testpaths = src/tests`)
- Pattern: Inject `FakeMPV` / `FakeMPVPlayer` via `app.mpv = ...`
- Stub `app.query_one` and `app.update_now_playing` to avoid Textual DOM
- Use `asyncio.run()` for async methods (pytest-asyncio is NOT installed)
- Run: `uv run pytest -q` from repo root (expects 59 passed)
- Every pytest run also refreshes the SQLite inventory `testsuite.db`; view it with
  `uv run python scripts/report_testsuite_db.py` (rebuild/enrich via
  `scripts/update_testsuite_db.py`). The `network`-marked radio test auto-skips offline.

## Linting/Formatting

Ruff configured in `pyproject.toml`:
- Line length: 100
- Target: py312
- Rules: E, F, I, UP, B
- Fix on save enabled

## Commit Message Convention

Follow the repo's established format — a `WIP:` prefix, a short present-tense summary,
and a timestamp. This matches the existing history (e.g.
`WIP: Fix TUI launch entry point + add tui boot demo Aug 29 2026, 23:55`).

Format:
```
WIP: <short summary> <Mon DD YYYY, HH:MM>
```

Rules:
- Prefix every commit with `WIP:` (no other prefixes like `feat:`/`fix:`/`docs:`).
- Use a short, present-tense, human-readable summary of the change.
- Append the date and time in `Mon DD YYYY, HH:MM` form (e.g. `Aug 30 2026, 14:05`).
- For feature branches, one `WIP:` commit per logical step is fine; squash is not required
  before merge (the merge itself uses a `--no-ff` merge commit).

## Debugging

Set `PYTUIP_DEBUG=1` environment variable for debug tracing (stack traces on `update_now_playing` calls, error logging in `on_now_playing_message`).

Set `PYTUIP_PROFILE=1` to enable performance profiling (logs execution times at DEBUG level to `pytuiplayer.performance` logger).

## Profiling

Profiling decorators (`@profile`, `@profile_async`) from `pytuiplayer.profiling` are applied to all critical UI event handlers, render methods, and async operations. When `PYTUIP_PROFILE=1` is set, each profiled method logs its execution time in milliseconds. When disabled (default), the decorators add near-zero overhead (single env var check).

Profiled methods include:
- All render methods (NowPlaying, ProgressBar, VolumeIndicator)
- All action handlers (play, pause, stop, seek, volume, mute)
- Event handlers (on_mount, on_button_pressed, on_list_view_selected, etc.)
- Async loaders (load_stations, load_local_files, load_m3u, _load_json)
- Polling callbacks (update_progress, _refresh_metadata)
- UI updates (update_now_playing, update_volume_ui)

## Common Pitfalls

1. **`fetch_duration` is an `async def` class method** spawned via `self.run_worker(self.fetch_duration, item)` from `load_local_files`. Keep its worker-trigger flag named `self.fetch_duration_eager` — never name a spawned worker the same as a bool flag.
2. `max_playlist_items` is assigned exactly once in `__init__`, from the `MAX_PLAYLIST_ITEMS` class constant (2000). Do not re-assign it elsewhere.
3. **Silent exception swallowing**: Most methods have bare `try/except: pass` — intentional to keep TUI alive, but makes debugging hard.
4. **Screen abstraction**: Mode switching uses `RadioScreen`/`LocalScreen` via `switch_screen()`, not manual visibility toggling. `app.query_one` delegates to the active screen.
5. **`update_now_playing` single path**: Posts a message only — no direct-assignment fallback.
6. **`item.data` shape**: Unified `ItemData(source, title, duration, meta)` TypedDict. All producers (load_local_files, load_m3u) emit the same keys.
7. **`_meta_label` attribute**: Set on items by `load_m3u` but NOT by `load_local_files` — tests must account for this difference.
8. **Station loading on RadioScreen**: `RadioScreen.on_mount` reloads stations if `app.stations` is None OR if `station_list.children` is empty (handles switch-back from LocalScreen).

## Rules for Modifying Existing Components

1. Always inject `FakeMPV` in tests — never use real mpv in unit tests.
2. Stub `app.query_one` and `app.update_now_playing` to avoid Textual DOM dependencies.
3. Keep the defensive `try/except` pattern for UI updates (prevents TUI crashes).
4. Maintain backward compatibility for `item.data` shapes (dict vs Path/str).
5. Test both radio and local mode paths.
6. Run `uv run pytest -q` and `uv run ruff check .` before finishing.
7. Add `@profile` / `@profile_async` decorators to new render methods, event handlers, and async operations.
8. When adding a new test file, add its description to `FILE_DESCRIPTIONS` in `scripts/update_testsuite_db.py`.

## Rules for Adding New Components

1. Add widgets to `widgets.py` (not `tui_app.py`).
2. Add screens to `screens.py` (not `tui_app.py`).
3. Use `reactive` for widget state that triggers re-render.
4. Use `Message` subclasses for cross-widget communication.
5. Add corresponding keyboard bindings to `BINDINGS` list.
6. Add tests in `src/tests/` following the `FakeMPV` injection pattern.
7. Update CSS in `musicplayer_tui.css` for new widget IDs.
8. Add `@profile` decorator to render methods and event handlers.

## Prepare to Commit Checklist

Before committing on a feature branch, run these to ensure the commit is reviewable:

1. **Tests pass:** `uv run pytest -q` → all passed (the `network` radio test may skip only when offline).
2. **Lint clean:** `uv run ruff check .` → `All checks passed!`
3. **Test count sanity:** verify the passed count matches expectations (no accidental triple-counting from conftest hooks — each test's setup/call/teardown should count as 1, not 3).
4. **Testsuite DB report clean:** `uv run python scripts/report_testsuite_db.py` → verify:
   - `passed` count matches actual test count (not inflated by setup/call/teardown double-counting)
   - All new test files have descriptions (non-zero `lines` count)
   - Backlog items correctly reflect done/pending status
5. **Review acceptance tests:** each feature's acceptance tests cover the feature's behavior (not just importability). Verify each test would fail if the feature were removed.
6. **Scripts/demos work:** `uv run python scripts/run_tui_app_demo.py` and `uv run python scripts/run_radio_demo.py` boot cleanly.
7. **Entry point works:** `uv run pytuiplayer` launches the TUI.
8. **Docs in sync:** `ROADMAP.md` and `docs/AI_TASK_STATE.md` reflect the branch's work.
