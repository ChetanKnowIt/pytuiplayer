from pytest import MonkeyPatch
from pytuiplayer.tui_app import MusicPlayerApp
from pathlib import Path


class FakeMPVPlayer:
    def __init__(self):
        self.paused = True
        self.calls = []

    def pause(self):
        self.paused = True
        self.calls.append("pause")

    def unpause(self):
        self.paused = False
        self.calls.append("unpause")

    def stop(self):
        self.calls.append("stop")

    def is_paused(self):
        return self.paused


def test_tui_toggle_play_and_stop():
    app = MusicPlayerApp()
    # inject fake player
    app.mpv = FakeMPVPlayer()

    # avoid touching the textual DOM during unit tests
    app.update_now_playing = lambda *a, **k: None

    # when initially paused True, toggle should unpause
    app.action_toggle_play()
    assert app.mpv.calls[-1] == "unpause"

    # toggling again should pause
    app.action_toggle_play()
    assert app.mpv.calls[-1] == "pause"

    # test action_stop resets fields and updates progress bar
    bar = type("B", (), {"progress": None, "duration": None})()
    app.query_one = lambda *a, **k: bar
    app.update_now_playing = lambda *a, **k: None

    app.action_stop()
    assert app.current_title == "Nothing playing"
    assert bar.progress == 0
    assert bar.duration == 0


def test_load_stations_ui_updates_list():
    from pytuiplayer.station_player import StationPlayer
    import asyncio

    app = MusicPlayerApp()
    app.mpv = FakeMPVPlayer()

    # Use a StationPlayer with known stations
    app.stations = StationPlayer(app.mpv, stations=[{"name": "One", "url": "u"}, {"name": "Two", "url": "v"}])

    class FakeListView:
        def __init__(self):
            self.items = []
        def clear(self):
            self.items.clear()
        async def mount(self, item):
            self.items.append(item)

    fake = FakeListView()
    app.query_one = lambda *a, **k: fake

    asyncio.run(app.load_stations_ui())

    assert len(fake.items) == 2
    assert getattr(fake.items[0], "data")["name"] == "One"


def test_progressbar_unknown_duration():
    from pytuiplayer.tui_app import ProgressBar

    bar = ProgressBar()
    bar.progress = 0
    bar.duration = 0

    assert bar.render() == "⏱ Duration unknown"


def test_progressbar_formats_mmss_and_shows_bar():
    from pytuiplayer.tui_app import ProgressBar

    bar = ProgressBar()
    bar.progress = 75    # 1:15
    bar.duration = 300   # 5:00

    s = bar.render()
    assert "01:15 / 05:00" in s
    assert s.startswith("[") and "]" in s


def test_seek_to_percent_uses_absolute_if_available() -> None:
    class FakeMPVSeek:
        def __init__(self):
            self.last_abs = None
            self._dur = 200
            self._pos = 20
        def get_duration(self):
            return self._dur
        def get_time_pos(self):
            return self._pos
        def seek_absolute(self, seconds):
            self.last_abs = seconds

    mpv = FakeMPVSeek()
    app = MusicPlayerApp()
    app.mpv = mpv

    app.action_seek_to_50()
    assert mpv.last_abs == 100


def test_seek_to_percent_no_duration_is_noop() -> None:
    class FakeMPVNoDur:
        def __init__(self):
            self.called = False
        def get_duration(self):
            return None
        def seek_absolute(self, seconds):
            self.called = True

    mpv = FakeMPVNoDur()
    app = MusicPlayerApp()
    app.mpv = mpv

    # Should not raise and should not call seek when duration is unknown
    app.action_seek_to_50()
    assert not mpv.called


def test_volume_up_down_and_mute() -> None:
    class FakeMPVVol:
        def __init__(self):
            self.last = None
        def set_volume(self, v):
            self.last = v

    mpv = FakeMPVVol()
    app = MusicPlayerApp()
    app.mpv = mpv

    # start with default 50
    assert app.volume == 50

    app.action_volume_up()
    assert app.volume == 55
    assert mpv.last == 55

    app.action_volume_down()
    assert app.volume == 50
    assert mpv.last == 50

    # mute
    app.action_toggle_mute()
    assert app.muted is True
    assert mpv.last == 0

    # unmute restores previous volume
    app.action_toggle_mute()
    assert app.muted is False
    assert app.volume == 50
    assert mpv.last == 50


def test_explicit_play_and_pause():
    app = MusicPlayerApp()
    app.mpv = FakeMPVPlayer()
    # avoid touching the textual DOM during unit tests
    app.update_now_playing = lambda *a, **k: None

    app.action_play()
    assert app.mpv.calls[-1] == "unpause"

    app.action_pause()
    assert app.mpv.calls[-1] == "pause"


def test_visibility_toggle_hides_unused_widgets():
    import types, asyncio

    app = MusicPlayerApp()
    # fake widgets to capture display/visible/disabled changes
    class W:
        def __init__(self):
            self.visible = None
            self.display = None
            self.disabled = None
        def clear(self):
            self.cleared = True
        async def mount(self, item):
            self.mounted = getattr(self, "mounted", [])
            self.mounted.append(item)

    station = W()
    local = W()
    tree = W()

    from pytuiplayer.tui_app import NowPlaying
    def query_one(sel, *a, **k):
        if sel == "#station-list":
            return station
        if sel == "#local-list":
            return local
        if sel == "#directory-tree":
            return tree
        # provide a simple NowPlaying for update_now_playing calls
        if sel == NowPlaying:
            nw = NowPlaying()
            return nw
        raise KeyError(sel)

    app.query_one = query_one

    # simulate switching to local
    event = types.SimpleNamespace(pressed=types.SimpleNamespace(id="local-option"))
    asyncio.run(app.on_radio_set_changed(event))

    assert local.visible is True or local.display is True
    assert station.visible is False or station.display is False

    # switch back to radio
    event = types.SimpleNamespace(pressed=types.SimpleNamespace(id="radio-option"))
    asyncio.run(app.on_radio_set_changed(event))

    assert station.visible is True or station.display is True
    assert local.visible is False or local.display is False


def test_progressbar_shows_radio_meta_when_streaming():
    from pytuiplayer.tui_app import ProgressBar, NowPlaying

    app = MusicPlayerApp()
    class FakePlayer:
        def get_time_pos(self):
            return None
        def get_duration(self):
            return None
    app.mpv = FakePlayer()

    # simulate radio playing
    app.option_mode = "radio"
    app.currently_playing = "radio"
    app.current_title = "Artist - Track"

    # fake query_one to return a ProgressBar instance
    bar = None
    def query_one(sel, *a, **k):
        nonlocal bar
        if sel == ProgressBar:
            if bar is None:
                bar = ProgressBar()
            return bar
        if sel == NowPlaying:
            nw = NowPlaying()
            return nw
        raise KeyError(sel)

    app.query_one = query_one

    app.update_progress()

    assert bar.meta == "Artist - Track"
    assert "Artist - Track" in bar.render()


def test_play_local_calls_mpv_and_sets_title():
    app = MusicPlayerApp()

    class FakeMPV:
        def __init__(self):
            self.last = None
        def play(self, source):
            self.last = source

    mpv = FakeMPV()
    app.mpv = mpv
    # avoid touching the textual DOM in unit tests
    app.update_now_playing = lambda *a, **k: None

    p = Path("/tmp/song.mp3")
    app.play_local(p)

    assert mpv.last == str(p)
    assert app.currently_playing == "local"
    assert app.current_title == p.stem


def test_directory_tree_selection_plays_file_when_local():
    import types, asyncio

    app = MusicPlayerApp()

    class FakeMPV:
        def __init__(self):
            self.last = None
        def play(self, source):
            self.last = source

    app.mpv = FakeMPV()
    app.option_mode = "local"
    app.update_now_playing = lambda *a, **k: None

    event = types.SimpleNamespace(path=str(Path("/tmp/other.mp3")))
    asyncio.run(app.on_directory_tree_file_selected(event))

    assert app.mpv.last == str(Path("/tmp/other.mp3"))


def test_play_local_uses_mutagen_tags_if_available(monkeypatch: MonkeyPatch):
    app = MusicPlayerApp()

    class FakeMPV:
        def __init__(self):
            self.last = None
        def play(self, source):
            self.last = source

    app.mpv = FakeMPV()
    app.update_now_playing = lambda *a, **k: None

    # inject a fake mutagen.File that returns dict-like metadata
    import sys, types
    fake_mutagen = types.SimpleNamespace(File=lambda *a, **k: {"album": ["MyAlbum"], "title": ["MyTitle"]})
    monkeypatch.setitem(sys.modules, 'mutagen', fake_mutagen)

    p = Path("/tmp/tagged.mp3")
    app.play_local(p)

    assert app.current_title == "MyAlbum - MyTitle"


def test_load_m3u_parses_and_populates(tmp_path: Path):
    # create a small m3u playlist with metadata and relative path
    p = tmp_path / "playlist.m3u"
    music1 = tmp_path / "song1.mp3"
    music2 = tmp_path / "song2.mp3"
    music1.write_text("")
    music2.write_text("")

    content = """#EXTM3U
#EXTINF:123,Artist A - Title A
song1.mp3
song2.mp3
"""
    p.write_text(content)

    app = MusicPlayerApp()

    class FakeList:
        def __init__(self):
            self.items = []
        def clear(self):
            self.items.clear()
        async def mount(self, item):
            self.items.append(item)

    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    import asyncio
    asyncio.run(app.load_m3u(p))

    assert len(fake.items) == 2
    # loader now stores a dict with source and meta without resolving paths
    assert isinstance(getattr(fake.items[0], 'data'), dict)
    assert getattr(fake.items[0], 'data')['source'].endswith('song1.mp3')
    # our loader adds a `_meta_label` attribute to help testing/inspection
    assert getattr(fake.items[0], '_meta_label') == 'Artist A - Title A'


def test_load_large_m3u_is_truncated_and_batched(tmp_path: Path, monkeypatch: MonkeyPatch):
    # Create a large playlist (3k entries)
    p = tmp_path / "big.m3u"
    n = 3000
    with open(p, "w") as f:
        f.write("#EXTM3U\n")
        for i in range(n):
            f.write(f"#EXTINF:123,Title {i}\n")
            f.write(f"song{i}.mp3\n")

    app = MusicPlayerApp()
    # set a lower max to make the test deterministic
    app.max_playlist_items = 1000
    app.playlist_batch_size = 100

    class FakeList:
        def __init__(self):
            self.items = []
        def clear(self):
            self.items.clear()
        async def mount(self, item):
            self.items.append(item)

    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    # track that we yield to event loop by monkeypatching asyncio.sleep
    import asyncio
    calls = {"sleep_called": 0}
    async def fake_sleep(t):
        calls["sleep_called"] += 1
        # do not actually delay tests
        return
    monkeypatch.setattr(asyncio, "sleep", fake_sleep)

    asyncio.run(app.load_m3u(p))

    # We expect truncation to max_playlist_items
    assert len(fake.items) == 1000
    # and we expect at least one batch yield to have occurred
    assert calls["sleep_called"] >= 1


def test_playlist_item_uses_extinf_metadata_on_play():
    """Selecting a playlist item created by `load_m3u` should use the
    playlist `#EXTINF` metadata as the displayed `current_title` when played.
    """
    import types, asyncio

    app = MusicPlayerApp()

    class FakeMPV:
        def __init__(self):
            self.last = None
        def play(self, source):
            self.last = source

    app.mpv = FakeMPV()
    app.update_now_playing = lambda *a, **k: None
    app.option_mode = "local"

    # Create a fake list item as load_m3u now produces: {source, meta}
    from textual.widgets import ListItem, Label
    item = ListItem(Label("song.mp3"))
    item.data = {"source": "/tmp/song.mp3", "meta": "Artist X - Track Y"}

    # Build a simple event object expected by on_list_view_selected
    list_view = types.SimpleNamespace(id="local-list")
    event = types.SimpleNamespace(list_view=list_view, item=item)

    asyncio.run(app.on_list_view_selected(event))

    assert app.mpv.last == "/tmp/song.mp3"
    assert app.current_title == "Artist X - Track Y"


def test_play_playlist_starts_first_item():
    app = MusicPlayerApp()

    class FakeMPV:
        def __init__(self):
            self.last = None
        def play(self, source):
            self.last = source

    app.mpv = FakeMPV()
    app.update_now_playing = lambda *a, **k: None

    from textual.widgets import ListItem, Label
    item = ListItem(Label("song.mp3"))
    item.data = {"source": "/tmp/first.mp3", "meta": "First - Song"}

    class FakeList:
        def __init__(self, items):
            self.items = items

    fake = FakeList([item])
    app.query_one = lambda *a, **k: fake

    app.action_play_playlist()

    assert app.mpv.last == "/tmp/first.mp3"
    assert app.current_title == "First - Song"
