"""Integration test: DataTable row selection triggers playback.

This test verifies the full flow:
1. Load files into DataTable (local_items populated)
2. Select a row in the DataTable
3. Verify play_local is called with the correct item_data

This prevents the bug where files show in the widget but clicking them
does nothing (no audio plays, "Nothing playing" stays).
"""

import asyncio
from unittest.mock import MagicMock

from pytuiplayer.tui_app import MusicPlayerApp


class FakeMPV:
    """Fake MPV that records play calls."""

    def __init__(self):
        self.calls = []
        self._paused = True

    def play(self, source):
        self.calls.append(("play", source))

    def pause(self):
        self._paused = True

    def unpause(self):
        self._paused = False

    def stop(self):
        pass

    def seek(self, *a):
        pass

    def volume(self, *a):
        pass

    def get_property(self, *a, **k):
        return None


class FakeTable:
    """Fake DataTable that mimics Textual's API."""

    def __init__(self):
        self.rows = {}
        self.ordered_columns = []
        self._row_keys = []
        self.cursor_row = None
        self.border_title = ""
        self.cursor_type = ""
        self.zebra_stripes = False
        self.id = "local-list"

    def clear(self):
        self.rows.clear()
        self._row_keys.clear()

    def add_row(self, *values, key=None):
        if len(values) > len(self.ordered_columns):
            raise ValueError("More values provided than there are columns.")
        self.rows[key] = values
        self._row_keys.append(key)

    def add_columns(self, *labels):
        for label in labels:
            self.ordered_columns.append(label)

    def update_cell(self, row_key, col_key, value):
        pass

    @property
    def ordered_rows(self):
        return []


class FakeStatic:
    def __init__(self):
        self.text = ""

    def update(self, text):
        self.text = text


class FakeNowPlaying:
    def __init__(self):
        self.title = ""
        self.state = ""
        self.source = ""
        self.connecting = False
        self.meta = ""
        self._khz = "44.1"
        self._kbps = "320"


class FakeVolumeIndicator:
    def __init__(self):
        self.volume = 50
        self.muted = False


def _make_app_with_local_files(tmp_path):
    """Create an app with local files loaded into a fake DataTable."""
    app = MusicPlayerApp()
    app.mpv = FakeMPV()
    app.now_playing_calls = []
    app.update_now_playing = lambda *a: None
    app.run_worker = lambda *a, **k: None
    app.option_mode = "local"  # Simulate being in local mode

    table = FakeTable()
    static = FakeStatic()
    now_playing = FakeNowPlaying()
    volume_indicator = FakeVolumeIndicator()

    def query_one(selector, *args, **k):
        if selector == "#local-list":
            return table
        if selector == "#loading-status":
            return static
        if selector == "#now-playing":
            return now_playing
        if selector == "#volume-indicator":
            return volume_indicator
        raise LookupError(f"No widget for {selector}")

    app.query_one = query_one

    # Create a real temp mp3 file
    mp3 = tmp_path / "test_song.mp3"
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)

    # Load local files
    asyncio.run(app.load_local_files(tmp_path))

    return app, table, static, mp3


def test_data_table_row_selected_plays_local_file(tmp_path):
    """Selecting a row in the local-list DataTable should call play_local."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    # Verify files are loaded
    assert len(app.local_items) >= 1, "No items loaded"
    assert len(table.rows) >= 1, "No rows in DataTable"

    # Find the row key for our test file
    row_key = str(mp3)
    assert row_key in app.local_items, f"Item not found in local_items: {row_key}"

    # Create a mock DataTable.RowSelected event
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    # Call the handler
    asyncio.run(app.on_data_table_row_selected(event))

    # Verify play was called
    play_calls = [c for c in app.mpv.calls if isinstance(c, tuple) and c[0] == "play"]
    assert len(play_calls) == 1, f"Expected 1 play call, got {len(play_calls)}. All calls: {app.mpv.calls}"
    assert play_calls[0][1] == str(mp3), f"Wrong file played: {play_calls[0][1]}"


def test_data_table_row_selected_sets_currently_playing(tmp_path):
    """After selecting a row, currently_playing should be set."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    row_key = str(mp3)
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    asyncio.run(app.on_data_table_row_selected(event))

    assert app.currently_playing == "local"
    assert app._current_local_source == str(mp3)


def test_data_table_row_selected_updates_title(tmp_path):
    """After selecting a row, current_title should be set."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    row_key = str(mp3)
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    asyncio.run(app.on_data_table_row_selected(event))

    assert app.current_title != "Nothing playing"
    assert app.current_title != ""


def test_data_table_row_selected_ignores_other_tables(tmp_path):
    """Row selection in other tables should be ignored."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    # Create a different table
    other_table = FakeTable()
    other_table.id = "other-table"

    row_key = str(mp3)
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = other_table
    event.row_key = row_key_obj
    event.cursor_row = 0

    asyncio.run(app.on_data_table_row_selected(event))

    # Should not play anything
    assert len(app.mpv.calls) == 0


def test_data_table_row_selected_ignores_radio_mode(tmp_path):
    """Row selection should be ignored in radio mode."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)
    app.option_mode = "radio"

    row_key = str(mp3)
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    asyncio.run(app.on_data_table_row_selected(event))

    # Should not play anything
    assert len(app.mpv.calls) == 0


def test_data_table_row_selected_missing_item(tmp_path):
    """Selecting a row with no matching item should not crash."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    row_key = "/nonexistent/path.mp3"
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 99

    # Should not raise
    asyncio.run(app.on_data_table_row_selected(event))

    # Should not play anything
    assert len(app.mpv.calls) == 0


def test_m3u_row_selected_plays_url_stream(tmp_path):
    """Selecting an M3U entry (URL stream) should play via URL branch."""
    app = MusicPlayerApp()
    app.mpv = FakeMPV()
    app.now_playing_calls = []
    app.update_now_playing = lambda *a: None
    app.run_worker = lambda *a, **k: None
    app.option_mode = "local"

    table = FakeTable()
    static = FakeStatic()
    now_playing = FakeNowPlaying()
    volume_indicator = FakeVolumeIndicator()

    def query_one(selector, *args, **k):
        if selector == "#local-list":
            return table
        if selector == "#loading-status":
            return static
        if selector == "#now-playing":
            return now_playing
        if selector == "#volume-indicator":
            return volume_indicator
        raise LookupError(f"No widget for {selector}")

    app.query_one = query_one

    # Create an M3U file with a URL
    m3u = tmp_path / "playlist.m3u"
    m3u.write_text("#EXTM3U\n#EXTINF:0,Test Stream\nhttp://example.com/stream.mp3\n")

    # Load M3U
    asyncio.run(app.load_m3u(m3u))

    assert len(app.local_items) >= 1, "No items loaded from M3U"

    # Get the URL key
    url = "http://example.com/stream.mp3"
    assert url in app.local_items, f"URL not found in local_items: {url}"

    # Create event
    row_key_obj = MagicMock()
    row_key_obj.value = url
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    asyncio.run(app.on_data_table_row_selected(event))

    # Verify play was called with URL
    play_calls = [c for c in app.mpv.calls if isinstance(c, tuple) and c[0] == "play"]
    assert len(play_calls) == 1, f"Expected 1 play call, got {len(play_calls)}"
    assert play_calls[0][1] == url, f"Wrong URL played: {play_calls[0][1]}"
    assert app._stream_source is True


def test_m3u_local_file_row_selected(tmp_path):
    """Selecting an M3U entry (local file) should play the local file."""
    app = MusicPlayerApp()
    app.mpv = FakeMPV()
    app.now_playing_calls = []
    app.update_now_playing = lambda *a: None
    app.run_worker = lambda *a, **k: None
    app.option_mode = "local"

    table = FakeTable()
    static = FakeStatic()
    now_playing = FakeNowPlaying()
    volume_indicator = FakeVolumeIndicator()

    def query_one(selector, *args, **k):
        if selector == "#local-list":
            return table
        if selector == "#loading-status":
            return static
        if selector == "#now-playing":
            return now_playing
        if selector == "#volume-indicator":
            return volume_indicator
        raise LookupError(f"No widget for {selector}")

    app.query_one = query_one

    # Create a real temp mp3 file
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)

    # Create an M3U file with a local file path
    m3u = tmp_path / "playlist.m3u"
    m3u.write_text(f"#EXTM3U\n#EXTINF:180,My Song\n{mp3}\n")

    # Load M3U
    asyncio.run(app.load_m3u(m3u))

    assert len(app.local_items) >= 1, "No items loaded from M3U"

    # Get the file key
    file_key = str(mp3)
    assert file_key in app.local_items, f"File not found in local_items: {file_key}"

    # Create event
    row_key_obj = MagicMock()
    row_key_obj.value = file_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    asyncio.run(app.on_data_table_row_selected(event))

    # Verify play was called with file path
    play_calls = [c for c in app.mpv.calls if isinstance(c, tuple) and c[0] == "play"]
    assert len(play_calls) == 1, f"Expected 1 play call, got {len(play_calls)}"
    assert play_calls[0][1] == str(mp3), f"Wrong file played: {play_calls[0][1]}"
    assert app._stream_source is False


def test_row_selected_does_not_crash_on_mpv_error(tmp_path):
    """If mpv.play crashes, the app should not crash."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    # Make mpv.play crash
    def crashing_play(source):
        raise RuntimeError("mpv crash!")

    app.mpv.play = crashing_play

    row_key = str(mp3)
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    # Should not raise
    asyncio.run(app.on_data_table_row_selected(event))

    # Should still be alive
    assert app.currently_playing is None or app.currently_playing == "local"


def test_row_selected_cached_file_does_not_crash(tmp_path):
    """Selecting a cached file should not crash the app."""
    app, table, static, mp3 = _make_app_with_local_files(tmp_path)

    # Simulate cached item
    app.metadata_index = MagicMock()
    app.metadata_index.get_track.return_value = {
        "path": str(mp3),
        "duration": 180,
        "sample_rate": 44100,
        "bitrate": 320000,
        "title": "Cached Song",
    }

    row_key = str(mp3)
    row_key_obj = MagicMock()
    row_key_obj.value = row_key
    event = MagicMock()
    event.data_table = table
    event.row_key = row_key_obj
    event.cursor_row = 0

    # Should not crash
    asyncio.run(app.on_data_table_row_selected(event))

    assert app.currently_playing == "local"
