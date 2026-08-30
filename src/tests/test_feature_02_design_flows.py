"""Acceptance tests for feature/02-fix-design-flows.

Verifies the structural debt fixes: Screen abstraction, single now-playing
update path, unified item.data shape, structured error handling, responsive
progress bar, and code split regression.
"""

import asyncio
import types
from pathlib import Path
from unittest.mock import patch

from pytuiplayer.constants import ICON_ERR, ICON_OK, MAX_PLAYLIST_ITEMS
from pytuiplayer.screens import LocalScreen, RadioScreen
from pytuiplayer.types import ItemData
from pytuiplayer.utils import fmt_mmss, parse_extinf, resolve_source
from pytuiplayer.widgets import NowPlaying, ProgressBar, VolumeIndicator


# ---------------------------------------------------------------------------
# Shared fakes (same pattern as test_backlog_coverage.py)
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


def _stub_app(app, mpv=None):
    """Attach a FakeMPV and neutralise DOM-touching methods for unit tests."""

    app.mpv = mpv or FakeMPV()
    app.update_now_playing = lambda *a, **k: None
    return app


# ---------------------------------------------------------------------------
# Acceptance test 1: Screen abstraction replaces visibility toggling
# ---------------------------------------------------------------------------
def test_radio_local_use_screens_not_visibility_toggle():
    """Mode switch mounts RadioScreen/LocalScreen and hides the other;
    no manual display/disabled toggling remains in on_radio_set_changed."""
    from pytuiplayer.tui_app import MusicPlayerApp

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

    # Switch to local mode
    event = types.SimpleNamespace(pressed=types.SimpleNamespace(id="local-option"))
    with patch.object(type(app), "screen", new_callable=lambda: property(lambda self: FakeScreen())), \
         patch.object(app, "switch_screen", side_effect=mock_switch):
        asyncio.run(app.on_radio_set_changed(event))

    assert app.option_mode == "local"
    assert "LocalScreen" in screen_switches
    # No manual visibility/disabled toggling should occur
    assert widgets["#station-list"].visible is None
    assert widgets["#local-list"].disabled is None

    # Switch back to radio
    event = types.SimpleNamespace(pressed=types.SimpleNamespace(id="radio-option"))
    with patch.object(type(app), "screen", new_callable=lambda: property(lambda self: FakeScreen())), \
         patch.object(app, "switch_screen", side_effect=mock_switch):
        asyncio.run(app.on_radio_set_changed(event))

    assert app.option_mode == "radio"
    assert "RadioScreen" in screen_switches


# ---------------------------------------------------------------------------
# Acceptance test 2: Single now-playing update path
# ---------------------------------------------------------------------------
def test_update_now_playing_single_path():
    """update_now_playing updates the widget only via NowPlayingMessage;
    the direct-assignment fallback is removed."""
    from pytuiplayer.tui_app import MusicPlayerApp

    app = MusicPlayerApp()
    app.mpv = FakeMPV()
    # DO NOT override update_now_playing here - we want to test the real method

    # Track post_message calls
    posted_messages = []

    class FakeNowPlaying:
        def post_message(self, message):
            posted_messages.append(message)

        title = "Nothing playing"
        source = ""
        state = "⏹"

    fake_now = FakeNowPlaying()
    app.query_one = lambda sel, *a, **k: fake_now

    # Call update_now_playing
    app.update_now_playing("Test Song", "Radio", "▶")

    # Verify a message was posted (not direct assignment)
    assert len(posted_messages) == 1
    assert posted_messages[0].title == "Test Song"
    assert posted_messages[0].source == "Radio"
    assert posted_messages[0].state == "▶"

    # Verify internal state is preserved
    assert app.current_title == "Test Song"


# ---------------------------------------------------------------------------
# Acceptance test 3: Unified ItemData TypedDict
# ---------------------------------------------------------------------------
def test_item_data_unified_typeddict(tmp_path):
    """load_local_files, load_m3u, and radio selection all emit
    ItemData(source, title, duration, meta) with consistent keys."""
    from pytuiplayer.tui_app import MusicPlayerApp

    app = _stub_app(MusicPlayerApp())

    # --- Test 1: load_local_files emits ItemData ---
    class FakeList:
        def __init__(self):
            self.items = []
            self.index = None
        def clear(self):
            self.items.clear()
        async def mount(self, *items):
            self.items.extend(items)

    fake_list = FakeList()
    app.query_one = lambda *a, **k: fake_list
    app.run_worker = lambda *a, **k: None  # don't actually spawn workers

    # Create a temp mp3 file
    mp3_file = tmp_path / "test_song.mp3"
    mp3_file.write_text("")

    asyncio.run(app.load_local_files(tmp_path))

    assert len(fake_list.items) >= 1
    item = fake_list.items[0]
    assert isinstance(item.data, dict)
    # ItemData keys present
    assert "source" in item.data
    assert "title" in item.data
    assert "duration" in item.data
    # source should be the Path, title should be the filename
    assert item.data["title"] == "test_song.mp3"
    assert item.data["duration"] is None

    # --- Test 2: load_m3u emits ItemData ---
    m3u_file = tmp_path / "playlist.m3u"
    m3u_file.write_text("#EXTINF:213,Song Title\nsong1.mp3\n")

    fake_list2 = FakeList()
    app.query_one = lambda *a, **k: fake_list2

    asyncio.run(app.load_m3u(m3u_file))

    assert len(fake_list2.items) >= 1
    item2 = fake_list2.items[0]
    assert isinstance(item2.data, dict)
    # All ItemData keys present
    assert "source" in item2.data
    assert "title" in item2.data
    assert "duration" in item2.data
    assert "meta" in item2.data
    # Verify EXTINF metadata is parsed
    assert item2.data["duration"] == 213
    assert item2.data["meta"] == "Song Title"


# ---------------------------------------------------------------------------
# Acceptance test 4: Structured error handling (no silent exceptions)
# ---------------------------------------------------------------------------
def test_no_silent_exceptions(caplog):
    """Bare except: pass replaced with logger.warning/logger.exception;
    assert expected errors are logged, not swallowed."""
    import logging

    from pytuiplayer.tui_app import MusicPlayerApp

    app = _stub_app(MusicPlayerApp())

    # Trigger an error in action_play (mpv will raise)
    class FailingMPV(FakeMPV):
        def unpause(self):
            raise RuntimeError("mpv failed")

    app.mpv = FailingMPV()

    with caplog.at_level(logging.WARNING):
        app.action_play()

    # Verify the error was logged (not silently swallowed)
    assert any("unpause" in msg or "mpv" in msg for msg in caplog.messages)


# ---------------------------------------------------------------------------
# Acceptance test 5: ProgressBar responsive width
# ---------------------------------------------------------------------------
def test_progressbar_uses_widget_width():
    """Bar length derives from self.size.width (minus padding),
    not a hardcoded 160."""
    from unittest.mock import patch

    bar = ProgressBar()
    bar.progress = 50
    bar.duration = 100

    # Mock widget size
    class FakeSize:
        width = 200

    class SmallSize:
        width = 50

    # Patch the size property
    with patch.object(type(bar), "size", new_callable=lambda: property(lambda self: FakeSize())):
        rendered = bar.render()

    # The bar should be present (Winamp-style: ─ and ● characters)
    assert "─" in rendered or "●" in rendered

    # With a smaller width, the bar should be shorter
    with patch.object(type(bar), "size", new_callable=lambda: property(lambda self: SmallSize())):
        small_rendered = bar.render()

    # Extract bar content: between start and " /" time marker
    import re
    large_bar = re.search(r'([─●]+)', rendered)
    small_bar = re.search(r'([─●]+)', small_rendered)

    assert large_bar and small_bar
    # The large width bar should be longer
    assert len(large_bar.group(1)) > len(small_bar.group(1))


# ---------------------------------------------------------------------------
# Acceptance test 6: Code split regression
# ---------------------------------------------------------------------------
def test_code_split_regression():
    """After extracting modules, all prior tests still pass
    (behavior unchanged)."""
    # Verify all modules are importable

    # Verify constants are accessible
    assert MAX_PLAYLIST_ITEMS == 2000
    assert ICON_OK == "⏺"
    assert ICON_ERR == "⚠"

    # Verify utils functions work
    assert fmt_mmss(125) == "02:05"
    assert fmt_mmss(None) == "--:--"
    assert parse_extinf("#EXTINF:213,Song Title") == (213, "Song Title")
    assert resolve_source(Path("/base"), "http://example.com") == "http://example.com"

    # Verify ItemData is a TypedDict
    data: ItemData = {"source": "/path", "title": "Test", "duration": None, "meta": "Test"}
    assert data["source"] == "/path"

    # Verify widget classes are importable and have expected attributes
    assert hasattr(NowPlaying, "on_now_playing_message")
    assert hasattr(ProgressBar, "render")
    assert hasattr(VolumeIndicator, "render")

    # Verify screens are importable and have expected attributes
    assert hasattr(RadioScreen, "compose_mode_content")
    assert hasattr(LocalScreen, "compose_mode_content")
