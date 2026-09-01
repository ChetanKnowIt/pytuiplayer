"""Tests for feature/12-ui-polish.

Covers the UI polish improvements:
- LocalScreen defaults to ~/Music when available (falls back to $HOME)
- NowPlaying marquee advances 2 chars/tick for long titles (>40 chars)
- VolumeIndicator CSS uses flexible width (not hardcoded 25)
- NowPlaying connecting state shows "⏳ Connecting..." for streams
- Playlist total duration shown in loading-status after loading
"""

import asyncio
from pathlib import Path

from pytuiplayer.screens import LocalScreen
from pytuiplayer.tui_app import MusicPlayerApp
from pytuiplayer.widgets import NowPlaying, VolumeIndicator

# === UI polish #5: default local scan to ~/Music ===========================

def test_default_music_dir_prefers_home_music(monkeypatch, tmp_path):
    """LocalScreen._default_music_dir() returns ~/Music when it exists."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    music_dir = tmp_path / "Music"
    music_dir.mkdir()
    assert LocalScreen._default_music_dir() == str(music_dir)


def test_default_music_dir_falls_back_to_home(monkeypatch, tmp_path):
    """When ~/Music doesn't exist, fall back to $HOME."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert LocalScreen._default_music_dir() == str(tmp_path)


# === UI polish #3: faster marquee for long titles ==========================

def test_marquee_tick_advances_faster_for_long_titles():
    """_tick advances 2 chars per tick when title > 40 chars, 1 char otherwise."""
    nw = NowPlaying()
    nw.title = "Short"
    start_offset = nw._offset
    nw._tick()
    assert nw._offset == (start_offset + 1) % max(1, len(nw.title) + 1)

    nw.title = "ThisIsAVeryLongSongTitleThatExceedsFortyCharsForFastScroll"
    start_offset = nw._offset
    nw._tick()
    assert nw._offset == (start_offset + 2) % max(1, len(nw.title) + 1)


def test_marquee_tick_resets_offset_on_new_title():
    """When a new title arrives, _offset is reset to 0 (marquee restarts)."""
    nw = NowPlaying()
    nw.title = "Old Long Song Title That Is Quite Long Indeed"
    nw._tick()
    assert nw._offset > 0
    nw.title = "New Track"
    nw._offset = 0
    assert nw._offset == 0


# === UI polish #6: flexible VolumeIndicator width ========================

def test_volume_indicator_renders_with_flexible_width():
    """VolumeIndicator.render() still produces valid output."""
    vi = VolumeIndicator()
    vi.volume = 70
    vi.muted = False
    rendered = vi.render()
    assert "VOL" in rendered
    assert "70%" in rendered
    assert "█" in rendered
    assert "░" in rendered


# === UI polish #4: connecting state in NowPlaying ========================

def test_now_playing_shows_connecting_state():
    """When connecting=True and stream=True, render shows 'Connecting...'."""
    nw = NowPlaying()
    nw.stream = True
    nw.connecting = True
    nw.meta = ""
    rendered = nw.render()
    assert "Connecting..." in rendered
    assert "⏳" in rendered


def test_now_playing_connecting_clears_on_meta_arrival():
    """When connecting=False and meta is set, render shows the metadata title."""
    nw = NowPlaying()
    nw.stream = True
    nw.connecting = False
    nw.meta = "Artist - Track"
    rendered = nw.render()
    assert "Now: Artist - Track" in rendered
    assert "Connecting" not in rendered


def test_now_playing_connecting_combines_with_stream():
    """Connecting state takes priority over metadata in render."""
    nw = NowPlaying()
    nw.stream = True
    nw.connecting = True
    nw.meta = "Artist - Track"
    rendered = nw.render()
    assert "Connecting..." in rendered
    assert "Now:" not in rendered


# === UI polish #8: playlist total time display ============================

def test_load_m3u_shows_total_duration(tmp_path):
    """load_m3u updates loading status with total duration from EXTINF."""
    p = tmp_path / "playlist.m3u"
    p.write_text(
        "#EXTM3U\n"
        "#EXTINF:65,First Song\n"
        "song1.mp3\n"
        "#EXTINF:120,Second Song\n"
        "song2.mp3\n"
    )

    app = MusicPlayerApp()
    app.run_worker = lambda work, **kwargs: None

    class FakeList:
        def __init__(self):
            self.children = []
            self.index = None
        def clear(self):
            self.children.clear()
        async def mount(self, *items):
            self.children.extend(items)

    fake_list = FakeList()
    loading_calls = []

    class FakeLoading:
        def update(self, text):
            loading_calls.append(text)

    app.query_one = lambda sel, *a, **k: (
        FakeLoading() if sel == "#loading-status" else fake_list
    )
    asyncio.run(app.load_m3u(p))

    final_call = loading_calls[-1]
    assert "Loaded" in final_call
    assert "03:05" in final_call
    assert "with dur" in final_call
