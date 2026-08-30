# MusicPlayer TUI

**MusicPlayer TUI** is a terminal-based music player built with [Textual](https://textual.textualize.io/) and [mpv](https://mpv.io/) via the `python-mpv` library. It allows you to play both internet radio stations and local music files through an intuitive text-based user interface (TUI).

## Features

- **Radio Playback** — stream internet radio stations from a JSON list, with live ICY/metadata titles shown in Now Playing.
- **Local Playback** — browse and play local MP3 files; tag-based titles (`artist - title`) with filename fallback.
- **M3U Playlists** — load `.m3u` / `.m3u8` playlists (local files or radio-stream URLs) with `#EXTINF` metadata; radio URLs play as streams with live metadata.
- **M3U Radio Lists** — a playlist of radio-station URLs is treated as live streams (correctly labeled "Radio" with metadata polling), not local files.
- **Directory Navigation** — file-tree browser to pick MP3s, M3U playlists, or station JSON files.
- **Playlist Playback** — play a playlist from the start with the `o` key (or the on-screen control).
- **Playlist Search/Filter** — type to filter loaded tracks by title (case-insensitive substring match). Press `/` to focus search, Escape to clear.
- **Prev/Next Navigation** — skip to previous or next track in the current list.
- **Playback Controls** — play, pause, stop, seek (±5s and 10%/50%/90%), volume up/down, mute.
- **Mode Switching** — switch between Radio and Local modes via radio buttons.
- **Winamp-Style UI** — LED display (position/time/khz/kbps), seek-bar progress (● marker), retro volume bar, amber/green theme.
- **Modern TUI** — built with Textual; responsive layout, loading indicators, marquee Now Playing.

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd pytuiplayer
```

2. Install dependencies using [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

> Make sure `mpv` is installed on your system and available in your PATH.

On Linux:

```bash
sudo apt install mpv
```

## Usage

Run the application:

```bash
uv run pytuiplayer
```

> `uv run pytuiplayer` launches the full Textual TUI (console-script entry point
> `pytuiplayer:main` → `MusicPlayerApp().run()`). `uv run python -m pytuiplayer`
> does the same via the package's `__main__.py`. Running the module file directly
> (`uv run src/pytuiplayer/tui_app.py`) will NOT launch the UI — `tui_app.py` has no
> `__main__` guard, so it just imports and exits.

Or directly:

```bash
python -m pytuiplayer
```

### Controls

| Key | Action |
|-----|--------|
| `q` | Quit the application |
| `space` | Toggle play/pause |
| `p` | Play |
| `k` | Pause |
| `s` | Stop |
| `h` / `l` | Seek -5s / +5s |
| `1` / `5` / `9` | Seek to 10% / 50% / 90% |
| `+` / `-` | Volume up / down |
| `m` | Toggle mute |
| `o` | Play playlist from start |
| `/` | Focus search input (Local mode) |
| `Escape` | Clear search / exit search focus |

### Navigating the UI

* **Radio Mode**:
  * View available radio stations in the station list.
  * Select a station to play it.
  * Optionally load a different JSON file with new stations.

* **Local Mode**:
  * Browse local directories for MP3 files.
  * Select a file to play it.
  * Load M3U playlists for batch playback.

## Configuration

* **Radio Stations**: Stored in a JSON file (`stations.json`) located in the `src/pytuiplayer/` directory. Example structure:

```json
[
    {"name": "Station 1", "url": "http://example.com/stream1"},
    {"name": "Station 2", "url": "http://example.com/stream2"}
]
```

* **Custom Station Files**: Select a different `.json` file from the directory tree in Radio mode to load new stations.

## Dependencies

* [Python 3.12+](https://www.python.org/downloads/)
* [Textual](https://textual.textualize.io/)
* [python-mpv](https://github.com/andre-d/python-mpv)
* [mpv](https://mpv.io/)
* [mutagen](https://mutagen.readthedocs.io/)
* [anyio](https://anyio.readthedocs.io/)

## Screenshots

*(TODO: screenshots of interface)*

## Verification

Use this quick checklist to manually verify the core behaviors of the TUI and to run the automated tests.

* Run automated tests:
  - Command: `uv run pytest -q`
  - Expected: **147 passed** (includes 1 `network`-marked radio integration test that auto-skips offline; every run also refreshes `testsuite.db`). The live count is the source of truth — re-run `uv run pytest -q` rather than trusting a hardcoded number.

* Manual UI checks (run from project root):
  1. Start the app: `uv run pytuiplayer`
  2. Verify **Radio** mode (default):
     - Station list is visible; local list and directory tree are hidden.
     - Select a station -> `Now Playing` updates with station name.
     - While streaming (unknown duration), the progress area shows `Now: <metadata>` when available.
  3. Verify **Local** mode:
     - Switch to Local -> local list and directory tree are visible; station list hidden.
     - Select an `.mp3` -> `Now Playing` shows `Album - Title` if tags are present, otherwise filename.
     - Loading large playlists may take time; the list mounts in batches to keep the UI responsive.
     - Progress bar shows `elapsed / total` when duration is known.
  4. Controls to try:
     - `space` -- toggle Play/Pause
     - `p` -- Play
     - `k` -- Pause
     - `s` -- Stop
     - `h` / `l` -- Seek -5s / +5s
     - `1` / `5` / `9` -- Seek to 10%/50%/90%
  5. Exit: Press `q` to quit the app.

* Troubleshooting:
  - If `Now Playing` does not show a title persistently, run with debug tracing:
    - Linux/macOS: `PYTUIP_DEBUG=1 uv run pytuiplayer` and reproduce; look for lines prefixed with `[PYTUIP DEBUG] update_now_playing called:`.
  - If radio metadata does not appear, ensure `mpv` supports ICY/media metadata for the stream and check the mpv logs printed to stdout.

## Packaging & Distribution

`pytuiplayer` can be installed/run from source or packaged into a standalone
executable.

### Install from source
```bash
git clone <repository-url>
cd pytuiplayer
uv sync --dev
uv run pytuiplayer
```

### Build a wheel / sdist
```bash
uv build            # produces dist/pytuiplayer-<version>-py3-none-any.whl + .tar.gz
pip install dist/*.whl
pytuiplayer
```

### Build a standalone executable (one-file)
Requires `mpv` installed on the **build** machine and on the **target** machine
(`python-mpv` loads the system `libmpv` shared library at runtime — it is not
bundled):
```bash
uv sync --dev
uv run python scripts/build_pyinstaller.py   # -> dist/pytuiplayer (or .exe on Windows)
./dist/pytuiplayer
```

### CI / CD
- `.github/workflows/ci.yml` — runs `ruff check` + `pytest` on every push/PR to
  `main` (the merge gate).
- `.github/workflows/build.yml` — on a `v*` tag (or manual dispatch) builds the
  wheel + sdist and one-file binaries for Linux / macOS / Windows, then drafts a
  GitHub release with all artifacts attached.

> Note: the bundled `pytuiplayer.spec` is the old PyInstaller spec (superseded by
> `scripts/build_pyinstaller.py`); it is `*.spec`-gitignored and retained for reference only.

### Troubleshooting (UI)
  - If the UI looks off, edit `src/pytuiplayer/musicplayer_tui.css` and use `textual run --dev` style live edits where applicable.
