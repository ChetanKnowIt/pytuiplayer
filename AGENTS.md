# AGENTS.md — pytuiplayer

## Project Overview

Terminal-based music player built with Python 3.12, Textual (TUI framework), and mpv. Supports two playback modes:
- **Radio mode**: Internet radio streams from a JSON station list
- **Local mode**: Local MP3 files and M3U playlists

## Key Files

| File | Role |
|------|------|
| `src/pytuiplayer/tui_app.py` | Main App (thin orchestrator — routes events to controllers) |
| `src/pytuiplayer/volume.py` | VolumeController — volume up/down/mute |
| `src/pytuiplayer/metadata.py` | MetadataPoller — stream/file metadata polling |
| `src/pytuiplayer/playlist.py` | PlaylistLoader + PlaylistNavigator — M3U/local loading + prev/next |
| `src/pytuiplayer/widgets.py` | NowPlaying, NowPlayingMessage, VolumeIndicator widgets |
| `src/pytuiplayer/screens.py` | ModeScreen, RadioScreen, LocalScreen |
| `src/pytuiplayer/constants.py` | MAX_PLAYLIST_ITEMS, ICON_OK, ICON_ERR |
| `src/pytuiplayer/utils.py` | Pure helpers: parse_extinf, resolve_source, fmt_mmss |
| `src/pytuiplayer/types.py` | ItemData TypedDict |
| `src/pytuiplayer/mpv_player.py` | Thin wrapper around `python-mpv` |
| `src/pytuiplayer/station_player.py` | Station list manager |
| `src/pytuiplayer/history.py` | HistoryTracker — playback history (feature/08) |
| `src/pytuiplayer/exporter.py` | PlaylistExporter — M3U export (feature/10) |
| `src/pytuiplayer/stations.json` | Default radio stations |
| `src/pytuiplayer/musicplayer_tui.css` | Textual CSS theme |
| `src/pytuiplayer/logging_config.py` | Logging configuration (setup_logging, get_logger) |
| `src/pytuiplayer/profiling.py` | Performance profiling decorators (@profile, @profile_async) |
| `src/pytuiplayer/__main__.py` | CLI entrypoint |
| `src/tests/` | Pytest test suite |
| `src/tests/testsuite_db.py` | SQLite test-inventory DB helpers (schema + idempotent upserts) |
| `src/tests/test_backlog_coverage.py` | ROADMAP Test Backlog coverage (22 tests) |
| `src/tests/test_feature_02_design_flows.py` | feature/02 acceptance tests (6 tests) |
| `src/tests/test_tui_app.py` | App actions, loaders, visibility, regressions (21 tests) |
| `scripts/` | Dev scripts and manual test scripts |
| `scripts/update_testsuite_db.py` | Rebuild/enrich `testsuite.db` (files + backlog mirror) |
| `scripts/report_testsuite_db.py` | Print the test inventory / backlog / runs |
| `pytuiplayer.spec` | PyInstaller build spec (legacy, `*.spec`-gitignored; superseded by build script) |
| `scripts/build_pyinstaller.py` | One-file PyInstaller build script (committed; `--collect-all` textual/mpv + data files) |
| `Makefile` | Local build pipeline: `make test` / `make lint` / `make build` / `make build-exe` / `make dist` |
| `.github/workflows/ci.yml` | CI gate: `ruff check` + `pytest` on push/PR to `main` |
| `.github/workflows/build.yml` | CD: on `v*` tag builds wheel/sdist + one-file binaries (Linux/macOS/Windows), drafts release |

## Architecture

### Textual App

`MusicPlayerApp(App)` in `tui_app.py` is a thin orchestrator. Business logic lives here, but widgets, screens, constants, helpers, and types are imported from their own modules:

- `widgets.py` — `NowPlaying`, `NowPlayingMessage`, `VolumeIndicator`
- `screens.py` — `ModeScreen` (base), `RadioScreen`, `LocalScreen`
- `constants.py` — `MAX_PLAYLIST_ITEMS`, `DEFAULT_PLAYLIST_BATCH_SIZE`, `ICON_OK`, `ICON_ERR`
- `utils.py` — `parse_extinf`, `resolve_source`, `fmt_mmss` (pure functions)
- `types.py` — `ItemData` TypedDict

`MusicPlayerApp.compose()` yields only `Header` + `Footer`; the active screen composes everything else. `MusicPlayerApp.query_one()` is overridden to delegate to the active screen so widgets inside pushed screens are found.

### Screen Abstraction

Mode switching uses Textual's screen stack (`RadioScreen` / `LocalScreen`), not manual visibility toggling. `RadioScreen` and `LocalScreen` extend `ModeScreen`, which composes shared widgets (Header, Footer, NowPlaying, controls, RadioSet) and calls `compose_mode_content()` for mode-specific content.

```
MusicPlayerApp
  └─ push_screen(RadioScreen)   # radio mode → station list
  └─ push_screen(LocalScreen)   # local mode → directory tree + local list
```

`ModeScreen` uses a `_radio_value` property (overridden by subclasses) to set which RadioButton is selected. `on_mount` syncs shared widget state from the app and defers data loading via `set_timer(0.1, ...)` so widgets are ready before population.

### Widgets (in widgets.py)

| Widget | Type | Purpose |
|--------|------|---------|
| `NowPlaying(Static)` | Reactive | Combined LED display + seek bar (2-row compact widget) |
| `NowPlayingMessage(Message)` | Message | Single update path from `update_now_playing()` to `NowPlaying` |
| `VolumeIndicator(Static)` | Reactive | Volume/mute display |

The old `ProgressBar` widget was merged into `NowPlaying` (feature/06) to eliminate a separate row and create a more compact Winamp-style layout. `NowPlaying` renders 2 rows: the LED display (row 1) and the seek bar / stream metadata (row 2).

### Controller Architecture

The app follows a thin-orchestrator pattern: `MusicPlayerApp` only routes Textual events to focused controllers.

| Controller | Module | Responsibility |
|------------|--------|----------------|
| `VolumeController` | `volume.py` | Volume up/down/mute, widget sync |
| `MetadataPoller` | `metadata.py` | Stream icy-title + local file tag polling |
| `PlaylistLoader` | `playlist.py` | Load M3U + local files, fetch durations |
| `PlaylistNavigator` | `playlist.py` | Prev/next navigation in local/radio lists |
| `HistoryTracker` | `history.py` | Playback history (records/replays recent items) |

`MusicPlayerApp.__init__` instantiates these controllers. Event handlers call them directly:
- `action_volume_up()` → `self.volume_controller.action_volume_up()`
- `_refresh_metadata()` → `self.metadata_poller.refresh()`
- `load_local_files(path)` → `self.playlist_loader.load_local_files(path)`
- `play_previous()` → `self.playlist_navigator.play_previous()`

This keeps `tui_app.py` focused on app lifecycle, event routing, and UI update paths.

- **Reactive widget state**: Textual `reactive` descriptor on widget attributes (`title`, `state`, `progress`, `duration`, `volume`, `muted`, `_offset`)
- **App-level state**: Plain attributes on `MusicPlayerApp` (`volume`, `muted`, `current_title`, `option_mode`, `currently_playing`, `_prev_volume`)
- **Unified item.data**: `ItemData(source, title, duration, meta)` TypedDict — `load_local_files` and `load_m3u` both emit this shape. Radio stations still use the raw `{"name":..., "url":...}` dict.
- **Message pattern**: `NowPlayingMessage(Message)` posted from `update_now_playing()` to `NowPlaying` widget; handler `on_now_playing_message` updates widget fields (single path — no direct-assignment fallback)

### Event Flow

- `on_mount()`: Initializes volume, sets up polling intervals, pushes `RadioScreen`
- `RadioScreen.on_mount`: Syncs shared widget state, loads stations via `set_timer(0.1, ...)` (reloads if `app.stations` is None OR list is empty, handling switch-back)
- `LocalScreen.on_mount`: Syncs shared widget state, loads local files via `set_timer(0.1, ...)`. Timer is stored in `self._pending_local_load` so it can be cancelled when an M3U is loaded.
- `on_radio_set_changed()`: Mode switching via `switch_screen(RadioScreen)` / `switch_screen(LocalScreen)`. Clears `_stream_source`, `currently_playing`, and `current_title` to prevent stale metadata.
- `on_button_pressed()`: Play/Pause/Stop/Prev/Next button handlers
- `on_list_view_selected()`: Station/local list selection
- `on_directory_tree_file_selected()`: File browser selection (JSON/M3U/MP3). For M3U files, cancels the pending local-file scan before loading.
- Polling: `update_progress()` (0.5s), `metadata_poller.refresh()` (1.0s)
- Marquee: `NowPlaying._tick()` (0.5s interval)
- Search: `LocalScreen._filter_local_list()` rebuilds ListView items from stored data. Uses `remove_children()` + `asyncio.sleep(0)` yields to avoid Textual timing bugs.

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
| `o` | Play playlist from start |
| `H` | Replay last played item (playback history) |
| `z` | Toggle shuffle mode |
| `r` | Cycle repeat mode (off → one → all) |
| `e` | Export playlist to M3U |
| `/` | Focus search input (Local mode) |

### Audio Architecture

- `MPVPlayer`: Wraps `python-mpv` (`mpv.MPV`). Supports DI via `player=` or `player_factory=` constructor args. Defensive `hasattr` checks for seek/duration across binding versions.
- `StationPlayer`: Holds `[{"name":..., "url":...}]` list, `play(index)` delegates to `MPVPlayer.play(url)`.
- Metadata polling via `_refresh_metadata()` (ICY/media-title from mpv properties).

### Library/Database

No runtime database — the app is file-based:
- Radio: JSON station files (`stations.json`), loaded via `anyio.open_file` async I/O
- Local: `load_local_files()` iterates directory for `.mp3`, creates `ListItem` with `ItemData(source=Path, title=str, duration=None)`
- M3U: `load_m3u()` parses `#EXTINF` metadata, resolves relative paths, batched mounting (200/batch, max 2000 via `MAX_PLAYLIST_ITEMS`), emits `ItemData(source, title, duration, meta)`

Note: the test suite maintains a *generated* SQLite inventory at the repo root
(`testsuite.db`) for tracking tests/backlog/runs. It is gitignored and refreshed on
every `uv run pytest` run (see `src/tests/testsuite_db.py`). It is not app data.

### Duration Fetching

- `fetch_duration(self, item_data)`: a plain `async def` method in `PlaylistLoader` that reads the file tag via the module-level `MutagenFile` binding, stores `item_data["duration"]`, and finds the visible widget in the ListView to update its label. It is launched off the main thread from `load_local_files` via `self.app.run_worker(partial(self.fetch_duration, item), ...)`. The worker receives the data dict (not the widget) because widgets can't survive a `clear()`+`mount()` cycle.
- `_populate_missing_durations(list_view)`: optional async background task in `PlaylistLoader` that fills missing durations for already-mounted items. It handles Path/string/URL sources (skips URLs and non-existent files) and is enabled only when `self.fetch_duration_eager` is `True`.

## Testing

- Framework: pytest
- Config: `pytest.ini` (`testpaths = src/tests`)
- Pattern: Inject `FakeMPV` / `FakeMPVPlayer` via `app.mpv = ...`
- Stub `app.query_one` and `app.update_now_playing` to avoid Textual DOM
- Use `asyncio.run()` for async methods (pytest-asyncio is NOT installed)
- Run: `uv run pytest -q` from repo root (currently **147 passed**; the `network`-marked radio test auto-skips offline, and is skipped entirely in CI). The live count is the source of truth — re-run `uv run pytest -q` rather than trusting a hardcoded number.
- Every pytest run also refreshes the SQLite inventory `testsuite.db`; view it with
  `uv run python scripts/report_testsuite_db.py` (rebuild/enrich via
  `scripts/update_testsuite_db.py`). The `network`-marked radio test auto-skips offline.

### Testsuite DB (testsuite.db)

The full test inventory — including the test backlog (missing/integration tests) and their
done/pending status — lives **exclusively** in a structured SQLite database
(`testsuite.db` at the repo root). ROADMAP.md stays light; the DB is the single source of
truth for everything test-related.

- **Schema:** `files`, `tests`, `runs`, `backlog`, `meta` (see `src/tests/testsuite_db.py`).
  Upsert keyed on `(file, name)` — reruns are idempotent.
- **Auto-refresh:** every `uv run pytest` run writes the `tests` + `runs` tables via
  the hook in `src/tests/conftest.py`. Only the `call` phase is counted (not setup/teardown)
  to avoid triple-counting.
- **Enrichment:** `scripts/update_testsuite_db.py` refreshes `files` (line counts +
  descriptions) and mirrors the Test Backlog into `backlog` (status preserved).
- **Reporting:** `scripts/report_testsuite_db.py` prints the inventory / backlog / runs.

```bash
uv run pytest -q                       # runs tests AND refreshes testsuite.db
uv run python scripts/update_testsuite_db.py   # enrich files + sync backlog
uv run python scripts/report_testsuite_db.py    # print the inventory
```

```sql
-- Quick queries against testsuite.db
SELECT file, COUNT(*) AS n FROM tests GROUP BY file ORDER BY file;
SELECT status, COUNT(*) FROM backlog GROUP BY status;          -- done vs pending
SELECT * FROM runs ORDER BY id DESC LIMIT 5;                   -- last runs
```

## Linting/Formatting

Ruff configured in `pyproject.toml`:
- Line length: 100
- Target: py312
- Rules: E, F, I, UP, B
- Fix on save enabled

## Packaging & Distribution

The app ships pure-Python (wheel + sdist) plus a one-file PyInstaller binary.

- **Build backend:** `uv_build` (`pyproject.toml`). `uv build` produces
  `dist/pytuiplayer-<ver>-py3-none-any.whl` + `.tar.gz`. Data files (`stations.json`,
  `musicplayer_tui.css`) are loaded via `Path(__file__).parent` and ARE included in the
  wheel (verified) — the console script `pytuiplayer:main` and `python -m pytuiplayer` both work.
- **Standalone binary:** `uv run python scripts/build_pyinstaller.py` (`--onefile`,
  `--collect-all textual --collect-all mpv`, bundles `stations.json` + `musicplayer_tui.css` into
  the package dir so the runtime path resolves). Output: `dist/pytuiplayer` (`.exe` on Windows).
- **Runtime requirement:** `python-mpv` loads the system `libmpv` at runtime via ctypes — it is
  NOT bundled. The target machine MUST have `mpv` installed and on PATH, on both build and run hosts.
- **Local pipeline:** `Makefile` wraps it (`make test`/`make lint`/`make build`/`make build-exe`/`make dist`).
- **CI/CD:** `.github/workflows/ci.yml` (ruff + pytest gate on `main` PRs) and
  `.github/workflows/build.yml` (on `v*` tag: wheel/sdist + per-OS one-file binaries, draft release).
- **Version:** bump `version` in `pyproject.toml` before tagging a release.
- **Release cadence (discipline):** cut a release **every 3 merged features** — bump the
  MINOR version and tag `v*.*.0` on `main` to let `build.yml` build + publish. Counter +
  ledger live in `docs/RELEASE_CADENCE.md`; `scripts/release_cadence.py` reports the count and
  whether a release is due. `mpv` stays independent of the package (target host must have it).
  See ROADMAP.md "Release Cadence Policy" for the full rule and versioning.

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
- All render methods (NowPlaying, VolumeIndicator)
- All action handlers (play, pause, stop, seek, volume, mute)
- Event handlers (on_mount, on_button_pressed, on_list_view_selected, etc.)
- Async loaders (load_stations, load_local_files, load_m3u, _load_json)
- Polling callbacks (update_progress, _refresh_metadata)
- UI updates (update_now_playing, update_volume_ui)

## Common Pitfalls

1. **`fetch_duration` is an `async def` class method** spawned via `self.run_worker(self.fetch_duration, item)` from `load_local_files`. Keep its worker-trigger flag named `self.fetch_duration_eager` — never name a spawned worker the same as a bool flag.
2. `max_playlist_items` is assigned exactly once in `__init__`, from the `MAX_PLAYLIST_ITEMS` class constant (2000). Do not re-assign it elsewhere.
3. **Structured error handling**: Methods use `logger.debug`/`logger.warning`/`logger.exception` instead of bare `except: pass`. The TUI stays alive but errors are visible in logs.
4. **Screen abstraction**: Mode switching uses `RadioScreen`/`LocalScreen` via `switch_screen()`, not manual visibility toggling. `app.query_one` delegates to the active screen.
5. **`update_now_playing` single path**: Posts a message only — no direct-assignment fallback.
6. **`item.data` shape**: Unified `ItemData(source, title, duration, meta)` TypedDict. `load_local_files` and `load_m3u` both emit this shape. Radio stations use the raw `{"name":..., "url":...}` dict (not ItemData).
7. **`_meta_label` attribute**: Set on items by `load_m3u` but NOT by `load_local_files` — tests must account for this difference.
8. **Station loading on RadioScreen**: `RadioScreen.on_mount` reloads stations if `app.stations` is None OR if `station_list.children` is empty (handles switch-back from LocalScreen).
9. **ListView timing**: `remove_children()` returns `AwaitRemove` that must be awaited, AND Textual needs several event loop cycles (`await asyncio.sleep(0)`) to complete internal widget tree updates. Mounting new items too quickly after removal causes empty children. Always create new items first, then remove old, then yield, then mount.
10. **Filter data vs widgets**: `app.local_items` stores **data dicts** (not widget references). Widgets can't be reused after `clear()`+`mount()`. Always rebuild fresh `ListItem` widgets from data when filtering.
11. **Mode switch state clearing**: `on_radio_set_changed` must clear `_stream_source` and `currently_playing` along with `current_title`. Otherwise the 1s `_refresh_metadata` poll reads stale mpv properties and overwrites "Nothing playing" with garbage.
12. **M3U load race condition**: `LocalScreen.on_mount` fires `set_timer(0.1, self._load_local)` which scans `$HOME`. When loading an M3U, `on_directory_tree_file_selected` must call `cancel_pending_local_load()` to prevent the timer from overwriting `local_items` with `$HOME` files.

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
