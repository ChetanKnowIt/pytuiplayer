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

---


