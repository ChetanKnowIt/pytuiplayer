"""Test coverage for the ROADMAP Test Backlog (testsuite/01-update-test-backlog).

These tests exercise the event handlers, action methods, and widgets of
``MusicPlayerApp`` using the FakeMPV injection pattern documented in SKILL.md
and references/worker_and_testing_patterns.md. No real mpv / TTY / network is
required, so the whole file runs under ``uv run pytest -q``.

Backlog items covered (ROADMAP "Test Backlog"):
  Missing Unit Tests #2-#20
  Integration / Widget Tests #1-#4
(Unit test #1, test_fetch_duration_updates_item_data, already lives in
test_tui_app.py.)
"""

import asyncio
import json
import types
from pathlib import Path

from pytuiplayer.station_player import StationPlayer
from pytuiplayer.tui_app import (
    MusicPlayerApp,
    NowPlaying,
    ProgressBar,
    VolumeIndicator,
)


# ---------------------------------------------------------------------------
# Shared fakes
# ---------------------------------------------------------------------------
class FakeMPV:
    """In-memory mpv backend that records every call."""

    def __init__(self):
        self.calls = []
        self._paused = True
        self._vol = 50
        self._pos = 0
        self._dur = 0
        self.player = None

    def play(self, source):
        self.calls.append(("play", source))

    def pause(self):
        self._paused = True
        self.calls.append("pause")

    def unpause(self):
        self._paused = False
        self.calls.append("unpause")

    def stop(self):
        self.calls.append("stop")

    def is_paused(self):
        return self._paused

    def set_volume(self, v):
        self._vol = v
        self.calls.append(("set_volume", v))

    def seek(self, delta):
        self.calls.append(("seek", delta))

    def get_time_pos(self):
        return self._pos

    def get_duration(self):
        return self._dur

    def seek_absolute(self, seconds):
        self.calls.append(("seek_absolute", seconds))


class IcyPlayer:
    """A fake ``mpv.player`` object that returns ICY/media-title metadata."""

    def __init__(self, title=None, media_title=None):
        self._title = title
        self._media = media_title

    def get_property(self, name):
        if name == "icy-title":
            return self._title
        if name == "media-title":
            return self._media
        return None


class FakeList:
    """Minimal ListView stand-in that records mounted items."""

    def __init__(self):
        self.items = []
        self.index = None

    def clear(self):
        self.items.clear()

    async def mount(self, *items):
        self.items.extend(items)


def _stub_app(app, mpv=None):
    """Attach a FakeMPV and neutralise DOM-touching methods for unit tests."""
    app.mpv = mpv or FakeMPV()
    app.update_now_playing = lambda *a, **k: None
    return app


# ===========================================================================
# Missing Unit Tests #2-#20
# ===========================================================================
def test_on_button_pressed_play_pause_stop():
    """#2 — button handlers forward to mpv correctly."""
    app = _stub_app(MusicPlayerApp())
    seen = []

    def recorder(*a, **k):
        seen.append(a)

    app.update_now_playing = recorder

    async def run():
        await app.on_button_pressed(types.SimpleNamespace(button=types.SimpleNamespace(id="play")))
        await app.on_button_pressed(types.SimpleNamespace(button=types.SimpleNamespace(id="pause")))
        await app.on_button_pressed(types.SimpleNamespace(button=types.SimpleNamespace(id="stop")))

    asyncio.run(run())

    assert "unpause" in app.mpv.calls
    assert "pause" in app.mpv.calls
    assert "stop" in app.mpv.calls
    # play/pause/stop each update the now-playing widget
    assert len(seen) == 3


def test_on_list_view_selected_station_mode():
    """#3 — selecting a station in radio mode triggers play_station (mpv.play)."""
    mpv = FakeMPV()
    app = MusicPlayerApp()
    app.mpv = mpv
    station = {"name": "Jazz FM", "url": "https://jazz.example/stream"}
    app.stations = StationPlayer(mpv, stations=[station])
    app.option_mode = "radio"

    station_list = FakeList()

    def query_one(sel, *a, **k):
        if sel == "#station-list":
            return station_list
        raise KeyError(sel)

    app.query_one = query_one
    app.update_now_playing = lambda *a, **k: None

    event = types.SimpleNamespace(
        list_view=types.SimpleNamespace(id="station-list"),
        item=types.SimpleNamespace(data=station),
    )
    asyncio.run(app.on_list_view_selected(event))

    assert ("play", "https://jazz.example/stream") in mpv.calls
    assert app.currently_playing == "radio"
    assert station_list.index == 0


def test_on_list_view_selected_local_mode():
    """#4 — selecting a local item triggers play_local (mpv.play with source)."""
    mpv = FakeMPV()
    app = _stub_app(MusicPlayerApp(), mpv=mpv)
    app.option_mode = "local"

    item_data = {"source": "/tmp/song.mp3", "meta": "Artist - Track"}
    event = types.SimpleNamespace(
        list_view=types.SimpleNamespace(id="local-list"),
        item=types.SimpleNamespace(data=item_data),
    )
    asyncio.run(app.on_list_view_selected(event))

    assert ("play", "/tmp/song.mp3") in mpv.calls
    assert app.current_title == "Artist - Track"
    assert app.currently_playing == "local"


def test_action_seek_forward_backward():
    """#5 — seek actions call mpv.seek with the correct delta."""
    app = _stub_app(MusicPlayerApp())
    app.action_seek_forward()
    app.action_seek_backward()
    assert ("seek", 5) in app.mpv.calls
    assert ("seek", -5) in app.mpv.calls


class FakeMPVNoAbsolute(FakeMPV):
    """Fake mpv backend that lacks the optional seek_absolute method.

    A property that raises AttributeError makes ``hasattr(self.mpv,
    "seek_absolute")`` return False, exactly as a real backend would when the
    binding does not expose absolute seeking.
    """

    @property
    def seek_absolute(self):
        raise AttributeError("seek_absolute not supported")


def test_action_seek_to_percent_no_absolute_fallback():
    """#6 — without seek_absolute, _seek_to_percent falls back to a relative seek."""
    mpv = FakeMPVNoAbsolute()
    mpv._dur = 200
    mpv._pos = 20
    app = _stub_app(MusicPlayerApp(), mpv=mpv)

    app.action_seek_to_50()  # target = 100, pos = 20 => seek(80)
    # the relative fallback path must have been taken (no seek_absolute recorded)
    assert all(c[0] != "seek_absolute" for c in mpv.calls)
    assert ("seek", 80) in mpv.calls


def test_update_progress_sets_bar_values():
    """#7 — update_progress pushes time/duration into the ProgressBar."""
    mpv = FakeMPV()
    mpv._pos = 42
    mpv._dur = 210
    app = _stub_app(MusicPlayerApp(), mpv=mpv)

    bar = ProgressBar()
    now = NowPlaying()

    def query_one(sel, *a, **k):
        if sel is ProgressBar:
            return bar
        if sel is NowPlaying:
            return now
        raise KeyError(sel)

    app.query_one = query_one
    app.update_progress()

    assert bar.progress == 42
    assert bar.duration == 210


def test_refresh_metadata_updates_title_for_radio():
    """#8 — ICY metadata updates current_title while radio is playing."""
    mpv = FakeMPV()
    mpv.player = IcyPlayer(title="Live Artist - Live Track")
    app = _stub_app(MusicPlayerApp(), mpv=mpv)
    app.option_mode = "radio"
    app.currently_playing = "radio"
    app.current_title = "Old Title"

    captured = []
    app.update_now_playing = lambda *a, **k: captured.append(a)

    app._refresh_metadata()

    assert app.current_title == "Live Artist - Live Track"
    assert captured and captured[0][0] == "Live Artist - Live Track"


def test_refresh_metadata_noop_for_local_mode():
    """#9 — no metadata polling happens outside radio mode."""
    mpv = FakeMPV()
    mpv.player = IcyPlayer(title="Should Not Appear")
    app = _stub_app(MusicPlayerApp(), mpv=mpv)
    app.option_mode = "local"
    app.currently_playing = "local"
    app.current_title = "Keep Me"

    app._refresh_metadata()

    assert app.current_title == "Keep Me"


def test_play_local_url_bypasses_file_checks():
    """#10 — a URL source is handed straight to mpv without file-resolution."""
    mpv = FakeMPV()
    app = _stub_app(MusicPlayerApp(), mpv=mpv)

    app.play_local({"source": "https://example.com/stream", "meta": "My Stream"})

    assert ("play", "https://example.com/stream") in mpv.calls
    assert app.currently_playing == "local"
    assert app.current_title == "My Stream"


def test_play_local_failure_shows_error():
    """#11 — when mpv.play raises, the UI is told playback failed."""

    class BoomMPV(FakeMPV):
        def play(self, source):
            raise RuntimeError("no decoder")

    app = MusicPlayerApp()
    app.mpv = BoomMPV()

    captured = []
    app.update_now_playing = lambda *a, **k: captured.append(a)

    app.play_local(Path("/tmp/does-not-exist.mp3"))

    assert captured
    assert captured[0][0] == "Failed to play file"


def test_load_m3u_respects_max_playlist_items(tmp_path: Path):
    """#12 — load_m3u truncates to self.max_playlist_items."""
    playlist = tmp_path / "small.m3u"
    lines = ["#EXTM3U\n"]
    for i in range(30):
        lines.append(f"#EXTINF:123,Title {i}\n")
        lines.append(f"song{i}.mp3\n")
    playlist.write_text("".join(lines))

    app = _stub_app(MusicPlayerApp())
    app.max_playlist_items = 10
    app.playlist_batch_size = 100

    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    asyncio.run(app.load_m3u(playlist))

    assert len(fake.items) == 10


def test_load_m3u_handles_aiofiles_and_sync_fallback(tmp_path: Path, monkeypatch):
    """#13 — load_m3u parses correctly with and without aiofiles (sync fallback)."""
    playlist = tmp_path / "p.m3u"
    playlist.write_text("#EXTM3U\n#EXTINF:123,Artist A - Title A\nsong1.mp3\n")

    # --- sync fallback path: force aiofiles to be unavailable ---
    monkeypatch.setattr("pytuiplayer.tui_app.aiofiles", None)
    app = _stub_app(MusicPlayerApp())
    fake = FakeList()
    app.query_one = lambda *a, **k: fake
    asyncio.run(app.load_m3u(playlist))

    assert len(fake.items) == 1
    assert fake.items[0].data["meta"] == "Artist A - Title A"

    # --- async path: only meaningful when aiofiles is actually installed ---
    try:
        import aiofiles  # noqa: F401
    except ImportError:
        return
    monkeypatch.setattr("pytuiplayer.tui_app.aiofiles", aiofiles)
    app2 = _stub_app(MusicPlayerApp())
    fake2 = FakeList()
    app2.query_one = lambda *a, **k: fake2
    asyncio.run(app2.load_m3u(playlist))
    assert len(fake2.items) == 1


def test_directory_tree_json_in_radio_mode(tmp_path: Path):
    """#14 — selecting a .json station file in radio mode reloads stations."""
    stations_json = tmp_path / "stations.json"
    stations_json.write_text(json.dumps([{"name": "A", "url": "u1"}, {"name": "B", "url": "u2"}]))

    mpv = FakeMPV()
    app = MusicPlayerApp()
    app.mpv = mpv
    app.option_mode = "radio"
    app.stations = StationPlayer(mpv, stations=[])

    mounted = FakeList()

    def query_one(sel, *a, **k):
        if sel == "#station-list":
            return mounted
        raise KeyError(sel)

    app.query_one = query_one
    app.notify = lambda *a, **k: None
    app.update_now_playing = lambda *a, **k: None

    event = types.SimpleNamespace(path=str(stations_json))
    asyncio.run(app.on_directory_tree_file_selected(event))

    assert len(app.stations.stations) == 2
    assert len(mounted.items) == 2


def test_directory_tree_unsupported_file_shows_error():
    """#15 — an unsupported file type posts an error notification."""
    app = _stub_app(MusicPlayerApp())
    app.option_mode = "local"

    captured = []
    app.notify = lambda msg, severity="information", **k: captured.append((msg, severity))

    event = types.SimpleNamespace(path="/tmp/notes.txt")
    asyncio.run(app.on_directory_tree_file_selected(event))

    assert captured
    assert captured[0][1] == "error"
    assert "unsupported" in captured[0][0].lower()


def test_volume_up_clamps_at_100():
    """#16 — volume never exceeds 100."""
    app = _stub_app(MusicPlayerApp())
    app.volume = 95
    app.muted = False

    app.action_volume_up()
    assert app.volume == 100
    app.action_volume_up()  # clamp
    assert app.volume == 100
    assert ("set_volume", 100) in app.mpv.calls


def test_volume_down_clamps_at_0_and_mutes():
    """#17 — volume floors at 0 and mutes at zero."""
    app = _stub_app(MusicPlayerApp())
    app.volume = 5
    app.muted = False

    app.action_volume_down()
    assert app.volume == 0
    assert app.muted is True
    assert ("set_volume", 0) in app.mpv.calls


def test_mute_restores_previous_volume():
    """#18 — unmuting restores the previously stored volume."""
    app = _stub_app(MusicPlayerApp())
    app.volume = 70
    app._prev_volume = 70
    app.muted = False

    app.action_toggle_mute()  # mute: remember 70, drop to 0
    assert app.muted is True
    assert app.volume == 70
    assert app._prev_volume == 70
    assert ("set_volume", 0) in app.mpv.calls

    app.action_toggle_mute()  # unmute: restore to 70
    assert app.muted is False
    assert app.volume == 70
    assert app.mpv._vol == 70


def test_now_playing_marquee_scrolls_long_titles():
    """#19 — the marquee scrolls long titles and wraps its offset."""
    nw = NowPlaying()
    nw.title = "ThisIsAVeryLongSongTitleThatShouldScroll"

    # No scrolling when width is None (deterministic in tests)
    assert nw._marquee() == nw.title

    # With a constrained width it returns a fixed-length slice
    slice_a = nw._marquee(12)
    assert len(slice_a) == 12

    # Ticking advances the offset (and wraps via modulo), changing the slice
    start_offset = nw._offset
    nw._tick()
    assert nw._offset != start_offset
    assert 0 <= nw._offset < len(nw.title) + 1


# ===========================================================================
# Integration / Widget Tests #1-#4
# ===========================================================================
def test_now_playing_widget_renders_countdown():
    """#1 — remaining time (countdown) shows in the NowPlaying render."""
    nw = NowPlaying()
    nw.duration = 300.0
    nw.progress = 75.0  # remaining = 225s => 03:45

    rendered = nw.render()
    assert "[03:45]" in rendered


def test_volume_indicator_shows_muted_state():
    """#2 — the volume indicator renders a mute glyph when muted."""
    vi = VolumeIndicator()
    vi.muted = True
    assert "🔇" in vi.render()

    vi.muted = False
    vi.volume = 42
    assert "🔊42" in vi.render()


def test_mode_switch_stops_playback():
    """#3 — switching mode stops current playback via mpv.stop()."""
    app = _stub_app(MusicPlayerApp())
    app.option_mode = "radio"

    # Avoid scanning the real home dir during the switch to local mode.
    async def noop(_path):
        return None

    app.load_local_files = noop

    widgets = {
        "#station-list": type("W", (), {"visible": None, "display": None, "disabled": None})(),
        "#local-list": type("W", (), {"visible": None, "display": None, "disabled": None})(),
        "#directory-tree": type("W", (), {"visible": None, "display": None, "disabled": None})(),
    }
    app.query_one = lambda sel, *a, **k: widgets[sel]

    event = types.SimpleNamespace(pressed=types.SimpleNamespace(id="local-option"))
    asyncio.run(app.on_radio_set_changed(event))

    assert "stop" in app.mpv.calls


def test_mode_switch_updates_visibility():
    """#4 — a mode switch changes the mode and triggers screen switch.

    With the screen abstraction, mode switching no longer toggles widget
    visibility directly; instead it switches between RadioScreen and LocalScreen.
    """
    from unittest.mock import patch

    app = _stub_app(MusicPlayerApp())
    app.option_mode = "radio"

    async def noop(_path):
        return None

    app.load_local_files = noop

    widgets = {
        "#station-list": type("W", (), {"visible": None, "display": None, "disabled": None})(),
        "#local-list": type("W", (), {"visible": None, "display": None, "disabled": None})(),
        "#directory-tree": type("W", (), {"visible": None, "display": None, "disabled": None})(),
    }
    app.query_one = lambda sel, *a, **k: widgets[sel]

    screen_switches = []

    def mock_switch(screen):
        screen_switches.append(type(screen).__name__)

    class FakeScreen:
        pass

    def switch_to(option_id):
        event = types.SimpleNamespace(pressed=types.SimpleNamespace(id=option_id))
        asyncio.run(app.on_radio_set_changed(event))

    # Patch screen property and switch_screen
    with patch.object(type(app), "screen", new_callable=lambda: property(lambda self: FakeScreen())), \
         patch.object(app, "switch_screen", side_effect=mock_switch):
        # radio -> local: mode changes to local, screen switches to LocalScreen
        switch_to("local-option")
        assert app.option_mode == "local"
        assert "LocalScreen" in screen_switches

        # local -> radio: mode changes to radio, screen switches to RadioScreen
        switch_to("radio-option")
        assert app.option_mode == "radio"
        assert "RadioScreen" in screen_switches
