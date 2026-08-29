# MusicPlayer TUI

**MusicPlayer TUI** is a terminal-based music player built with [Textual](https://textual.textualize.io/) and [mpv](https://mpv.io/) via the `python-mpv` library. It allows you to play both internet radio stations and local music files through an intuitive text-based user interface (TUI).

## Features

* **Terminal UI** with a modern TUI design using Textual.
* **Radio Playback**: Play your favorite internet radio stations from a JSON list.
* **Local Music Playback**: Browse and play MP3 files from your local directories.
* **M3U Playlist Support**: Load and play M3U playlists with metadata.
* **Directory Navigation**: Navigate your file system to select music files or radio station JSON files.
* **Playback Controls**: Play, pause, stop, seek, and volume control directly from the interface.
* **Mode Switching**: Switch between Radio and Local music modes using radio buttons.

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
  - Expected: **31 passed** (last run: 2026-08-29 23:29 IST; includes 1 `network`-marked radio integration test that auto-skips offline)

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
  - If the UI looks off, edit `src/pytuiplayer/musicplayer_tui.css` and use `textual run --dev` style live edits where applicable.
