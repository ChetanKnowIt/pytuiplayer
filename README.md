---

# MusicPlayer TUI

**MusicPlayer TUI** is a terminal-based music player built with [Textual](https://textual.textualize.io/) and [mpv](https://mpv.io/) via the `pytuiplayer` library. It allows you to play both internet radio stations and local music files through an intuitive text-based user interface (TUI).

## Features

* **Terminal UI** with a modern TUI design using Textual.
* **Radio Playback**: Play your favorite internet radio stations from a JSON list.
* **Local Music Playback**: Browse and play MP3 files from your local directories.
* **Directory Navigation**: Navigate your file system to select music files or radio station JSON files.
* **Playback Controls**: Play, pause, and stop music directly from the interface.
* **Mode Switching**: Switch between Radio and Local music modes using radio buttons.

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd <repository-directory>
```

2. Install the required dependencies:

```bash
pip install textual pytuiplayer
```

> Make sure `mpv` is installed on your system and available in your PATH.

On Linux:

```bash
sudo apt install mpv
```

## Usage

Run the application:

```bash
python music_player.py
```

### Controls

* **q**: Quit the application
* **Play Button**: Play selected radio station or local file
* **Pause Button**: Pause playback
* **Stop Button**: Stop playback

### Navigating the UI

* **Radio Mode**:

  * View available radio stations in the station list.
  * Select a station to play it.
  * Optionally load a different JSON file with new stations.

* **Local Mode**:

  * Browse local directories for MP3 files.
  * Select a file to play it.

## Configuration

* **Radio Stations**: Stored in a JSON file (`stations.json`) located in the same directory as the script. Example structure:

```json
[
    {"name": "Station 1", "url": "http://example.com/stream1"},
    {"name": "Station 2", "url": "http://example.com/stream2"}
]
```

* **Custom Station Files**: Select a different `.json` file from the directory tree in Radio mode to load new stations.

## Dependencies

* [Python 3.11+](https://www.python.org/downloads/)
* [Textual](https://textual.textualize.io/)
* [pytuiplayer](https://github.com/Flamm3o/pytuiplayer)
* [mpv](https://mpv.io/)

## Screenshots

*(TODO  screenshots of interface)*

## Verification v0.1.010320250200 — incremental testing and updates ✅

Use this quick checklist to manually verify the core behaviors of the TUI and to run the automated tests.

- Run automated tests:
  - Command: `uv run pytest -q`
  - Expected: **26 passed** (current test suite)

Changes in this incremental update:
- Added M3U playlist support with metadata and safe batched loading for large playlists.
- Improved local title selection (Album - Title preferred) and deferred metadata resolution until playback.
- Added message-based NowPlaying updates and tests to ensure marquee/progress reliability.

- Manual UI checks (run from project root):
  1. Start the app: `python src/test_main.py` (or your usual entry point)
  2. Verify **Radio** mode (default):
     - Station list is visible; local list and directory tree are hidden.
     - Select a station → `Now Playing` updates with station name.
     - While streaming (unknown duration), the progress area shows `Now: <metadata>` when available.
  3. Verify **Local** mode:
     - Switch to Local → local list and directory tree are visible; station list hidden.
     - Select an `.mp3` → `Now Playing` shows `Album - Title` if tags are present, otherwise filename.
     - Loading large playlists may take time; the list mounts in batches to keep the UI responsive.
     - Progress bar shows `elapsed / total` when duration is known.
  4. Controls to try:
     - `space` — toggle Play/Pause
     - `p` — Play
     - `k` — Pause
     - `s` — Stop
     - `h` / `l` — Seek -5s / +5s
     - `1` / `5` / `9` — Seek to 10%/50%/90%
  5. Exit: Press `q` to quit the app.

- Troubleshooting:
  - If `Now Playing` does not show a title persistently, run with debug tracing:
    - Linux/macOS: `PYTUIP_DEBUG=1 python src/test_main.py` and reproduce; look for lines prefixed with `[PYTUIP DEBUG] update_now_playing called:`.
  - If radio metadata does not appear, ensure `mpv` supports ICY/media metadata for the stream and check the mpv logs printed to stdout.
  - If the UI looks off, edit `src/pytuiplayer/musicplayer_tui.css` and use `textual run --dev` style live edits where applicable.

This verification checklist represents v0.1 of manual verification for the project. Please update as features change.

---


