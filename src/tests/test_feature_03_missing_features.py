"""Acceptance tests for feature/03-fix-missing-features.

Closes ROADMAP Missing Features / Gaps:
  #11 — local-file metadata polling (_refresh_metadata reads mutagen tags)
  #12 — action_play_playlist resolves items without relying on ListView.items
  #13 — keyboard binding for action_play_playlist
"""

from pathlib import Path
from unittest.mock import patch

from pytuiplayer.tui_app import MusicPlayerApp


# ---------------------------------------------------------------------------
# Shared fakes (same pattern as test_backlog_coverage.py / test_feature_02)
# ---------------------------------------------------------------------------
class FakePlayer:
    """Stands in for mpv's player object exposing get_property."""

    def __init__(self, props=None):
        self.props = props or {}

    def get_property(self, name):
        return self.props.get(name)


class FakeMPV:
    """In-memory mpv backend that records every call."""

    def __init__(self, props=None):
        self.calls = []
        self.player = FakePlayer(props)

    def play(self, source):
        self.calls.append(("play", source))

    def stop(self):
        self.calls.append("stop")

    def set_volume(self, v):
        self.calls.append(("set_volume", v))

    def get_time_pos(self):
        return 0

    def get_duration(self):
        return 0


class FakeItem:
    """Minimal stand-in for a Textual ListItem carrying item.data."""

    def __init__(self, data):
        self.data = data


class FakeListView:
    """List widget fake. `has_items=False` mimics real ListView (no .items)."""

    def __init__(self, children, has_items=True):
        self.children = children
        self.index = None
        if has_items:
            self.items = children


def make_app(mpv=None):
    """Build an app with no Textual DOM: fake mpv + stubbed UI hooks."""
    app = MusicPlayerApp()
    app.mpv = mpv or FakeMPV()
    app.now_playing_calls = []

    def _update(title="", source="", state=""):
        app.now_playing_calls.append((title, source, state))

    app.update_now_playing = _update
    app.query_one = lambda *a, **k: (_ for _ in ()).throw(LookupError("no DOM"))
    return app


# ---------------------------------------------------------------------------
# Gap #11 — local-file metadata polling
# ---------------------------------------------------------------------------
def test_local_metadata_polling_updates_title(tmp_path):
    """_refresh_metadata reads mutagen tags for local files and updates the title."""
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"\x00")

    app = make_app()
    app.option_mode = "local"
    app.currently_playing = "local"
    app._current_local_source = str(mp3)
    app.current_title = "track"

    tags = {"artist": ["Boards of Canada"], "title": ["Roygbiv"]}
    with patch("pytuiplayer.metadata.MutagenFile", return_value=tags):
        app._refresh_metadata()

    assert app.current_title == "Boards of Canada - Roygbiv"
    assert app.now_playing_calls[-1] == (
        "Boards of Canada - Roygbiv",
        "Local File",
        "▶",
    )


def test_local_metadata_polling_is_cached_per_source(tmp_path):
    """The 1s poll only reads tags once per source (no repeated mutagen calls)."""
    mp3 = tmp_path / "track.mp3"
    mp3.write_bytes(b"\x00")

    app = make_app()
    app.option_mode = "local"
    app.currently_playing = "local"
    app._current_local_source = str(mp3)

    tags = {"artist": ["A"], "title": ["B"]}
    with patch("pytuiplayer.metadata.MutagenFile", return_value=tags) as mock_tag:
        app._refresh_metadata()
        app._refresh_metadata()
        app._refresh_metadata()

    assert mock_tag.call_count == 1


def test_local_metadata_falls_back_to_media_title(tmp_path):
    """With no usable tags, the mpv media-title property is used instead."""
    mp3 = tmp_path / "untagged.mp3"
    mp3.write_bytes(b"\x00")

    app = make_app(FakeMPV({"media-title": "untagged.mp3"}))
    app.option_mode = "local"
    app.currently_playing = "local"
    app._current_local_source = str(mp3)
    app.current_title = "Nothing playing"

    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app._refresh_metadata()

    assert app.current_title == "untagged.mp3"


def test_radio_metadata_path_still_works():
    """Regression: radio mode still reads icy-title (gap #11 must not break it)."""
    app = make_app(FakeMPV({"icy-title": "Live Set — DJ X"}))
    app.option_mode = "radio"
    app.currently_playing = "radio"
    app._stream_source = True
    app.current_title = "Some Station"

    app._refresh_metadata()

    assert app.current_title == "Live Set — DJ X"
    assert app.now_playing_calls[-1] == ("Live Set — DJ X", "Radio", "▶")


def test_play_local_records_current_source(tmp_path):
    """play_local records the source so metadata polling knows what is playing."""
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"\x00")

    app = make_app()
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app.play_local({"source": mp3, "title": "song", "duration": None})

    assert app.currently_playing == "local"
    assert app._current_local_source == str(mp3.resolve())


# ---------------------------------------------------------------------------
# Gap #12 — robust playlist item resolution
# ---------------------------------------------------------------------------
def test_action_play_playlist_resolves_item():
    """action_play_playlist resolves via item.data with no AttributeError."""
    data = {"source": Path("/music/a.mp3"), "title": "A", "duration": None}
    view = FakeListView([FakeItem(data)])

    app = make_app()
    app.query_one = lambda *a, **k: view
    played = []
    app.play_local = played.append

    app.action_play_playlist()

    assert played == [data]
    assert view.index == 0


def test_action_play_playlist_without_items_attribute():
    """Real ListView lacks `.items` — children is used and nothing raises."""
    data = {"source": Path("/music/b.mp3"), "title": "B", "duration": None}
    view = FakeListView([FakeItem(data)], has_items=False)
    assert not hasattr(view, "items")

    app = make_app()
    app.query_one = lambda *a, **k: view
    played = []
    app.play_local = played.append

    app.action_play_playlist()

    assert played == [data]


def test_resolve_playlist_items_never_raises():
    """_resolve_playlist_items tolerates missing/empty/non-iterable attributes."""
    app = make_app()

    class Bare:
        pass

    assert app._resolve_playlist_items(Bare()) == []
    assert app._resolve_playlist_items(FakeListView([], has_items=False)) == []

    class BadItems:
        items = 42  # not iterable
        children = None

    assert app._resolve_playlist_items(BadItems()) == []


def test_action_play_playlist_reports_empty_playlist():
    """An empty list surfaces a warning instead of raising."""
    app = make_app()
    app.query_one = lambda *a, **k: FakeListView([], has_items=False)
    app.play_local = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("must not play")
    )

    app.action_play_playlist()

    assert app.now_playing_calls[-1] == ("No items in playlist", "", "⚠")


# ---------------------------------------------------------------------------
# Gap #13 — keyboard binding
# ---------------------------------------------------------------------------
def test_playlist_keyboard_binding_plays(tmp_path):
    """A binding maps to play_playlist and plays the first playlist item."""
    bindings = {
        b.key: b.action for b in MusicPlayerApp.BINDINGS if hasattr(b, "action")
    }
    assert "play_playlist" in bindings.values(), "no binding for action_play_playlist"

    key = next(k for k, action in bindings.items() if action == "play_playlist")

    mpv = FakeMPV()
    app = make_app(mpv)

    # Create real temp files
    mp3_first = tmp_path / "first.mp3"
    mp3_first.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    mp3_second = tmp_path / "2.mp3"
    mp3_second.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)

    data = {"source": mp3_first, "title": "First", "duration": None}
    view = FakeListView([FakeItem(data), FakeItem({"source": mp3_second})])
    app.query_one = lambda *a, **k: view

    # Invoke the action exactly as Textual's key dispatch would.
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        getattr(app, f"action_{bindings[key]}")()

    assert ("play", str(mp3_first)) in mpv.calls


# ---------------------------------------------------------------------------
# Bug fix — M3U radio URL entries must be treated as streams (not "Local File")
# ---------------------------------------------------------------------------
def test_play_local_url_is_flagged_stream():
    """A URL source (e.g. an M3U radio entry) plays as a stream, not a local file."""
    app = make_app()
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app.play_local({"source": "https://ice.somafm.com/groove-256-mp3",
                        "title": "Groove Salad", "duration": None})

    assert app.currently_playing == "local"
    assert app._stream_source is True
    # NowPlaying must label it "Radio", not "Local File"
    assert app.now_playing_calls[-1] == ("Groove Salad", "Radio", "▶")


def test_play_local_url_polls_stream_metadata():
    """An M3U radio URL entry gets icy-title polling via _refresh_stream_metadata."""
    app = make_app(FakeMPV({"icy-title": "Live — Groove Salad"}))
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app.play_local({"source": "https://ice.somafm.com/groove-256-mp3",
                        "title": "Groove Salad", "duration": None})
    app.current_title = "Groove Salad"

    app._refresh_metadata()

    assert app.current_title == "Live — Groove Salad"
    assert app.now_playing_calls[-1] == ("Live — Groove Salad", "Radio", "▶")


def test_play_local_filesystem_is_not_stream(tmp_path):
    """A local .mp3 path is NOT a stream and never triggers stream metadata polling."""
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"\x00")

    app = make_app()
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app.play_local({"source": mp3, "title": "song", "duration": None})

    assert app.currently_playing == "local"
    assert app._stream_source is False


def test_stop_clears_stream_flag():
    """Stopping playback clears both currently_playing and the stream flag."""
    app = make_app()
    app.currently_playing = "local"
    app._stream_source = True

    app.action_stop()

    assert app.currently_playing is None
    assert app._stream_source is False


def test_update_progress_meta_uses_stream_source():
    """The progress bar shows the stream title for M3U radio URLs too."""
    app = make_app(FakeMPV())
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app.play_local({"source": "https://ice.somafm.com/groove-256-mp3",
                        "title": "Groove Salad", "duration": None})
    app.current_title = "Groove Salad"

    class FakeBar:
        def __init__(self):
            self.meta = None

    bar = FakeBar()
    app.query_one = lambda *a, **k: bar
    app.update_progress()

    assert bar.meta == "Groove Salad"


# ---------------------------------------------------------------------------
# Dataset-driven test — real M3U radio list (assets/radio_stations_hq.m3u)
# ---------------------------------------------------------------------------
M3U_FIXTURE = Path(__file__).parent / "assets" / "radio_stations_hq.m3u"


def _mountable_list():
    """A list widget fake that captures mounted ListItems (mirrors load_m3u)."""

    class FakeList:
        def __init__(self):
            self.items = []

        def clear(self):
            self.items.clear()

        async def mount(self, *items):
            self.items.extend(items)

    return FakeList()


def test_load_real_radio_m3u_populates(tmp_path):
    """The real HQ radio playlist loads: CRLF, '#EXTINF:0,NAME', absolute URLs, ':' in titles."""
    src = tmp_path / "playlist.m3u"
    src.write_bytes(M3U_FIXTURE.read_bytes())

    app = make_app()
    fake = _mountable_list()
    app.query_one = lambda *a, **k: fake

    import asyncio

    asyncio.run(app.load_m3u(src))

    # 177 station entries in the dataset (one per non-comment stream line)
    assert len(fake.items) == 177
    first = fake.items[0]
    assert isinstance(first.data, dict)
    # Every entry is a network stream URL — never resolved to a local file path
    assert first.data["source"].startswith("http")
    assert first._meta_label == "- RP MELLOW"
    # A title containing ':' is preserved intact (SomaFM EXTINF on a single line)
    colon = next(it for it in fake.items if "SomaFM" in it._meta_label)
    assert "SomaFM - Soma Bossa Beyond" == colon._meta_label


def test_real_radio_m3u_entries_play_as_streams():
    """Selecting any entry from the real list routes through play_local URL branch: stream, 'Radio'."""
    import asyncio

    app = make_app()
    fake = _mountable_list()
    app.query_one = lambda *a, **k: fake
    asyncio.run(app.load_m3u(M3U_FIXTURE))

    # Simulate on_list_view_selected for the first station (item.data is a dict)
    entry = fake.items[0]
    with patch("pytuiplayer.metadata.MutagenFile", return_value=None):
        app.play_local(entry.data)

    assert app.currently_playing == "local"
    assert app._stream_source is True
    assert app.now_playing_calls[-1] == (entry._meta_label, "Radio", "▶")
    assert ("play", entry.data["source"]) in app.mpv.calls

