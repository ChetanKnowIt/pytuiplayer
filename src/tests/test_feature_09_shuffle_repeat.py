"""feature/09 acceptance tests — shuffle/repeat modes (ROADMAP Low Priority #4).

Covers the PlaylistNavigator index logic, the app toggle/cycle actions, and
integration with the local/radio lists. Uses a deterministic `_randrange`
injection so shuffle is testable without randomness.

Pattern: inject ``FakeMPVPlayer`` via ``app.mpv = ...``, stub ``query_one`` and
``update_now_playing`` to avoid the Textual DOM, and drive the methods directly.
"""

import asyncio
from pathlib import Path
from types import SimpleNamespace

from pytuiplayer.playlist import PlaylistNavigator
from pytuiplayer.tui_app import MusicPlayerApp


class FakeMPVPlayer:
    def __init__(self):
        self.calls = []

    def pause(self):
        self.calls.append("pause")

    def unpause(self):
        self.calls.append("unpause")

    def stop(self):
        self.calls.append("stop")

    def play(self, source):
        self.calls.append(("play", source))

    def is_paused(self):
        return True

    def set_volume(self, volume):
        self.calls.append(("vol", volume))

    def get_time_pos(self):
        return 0

    def get_duration(self):
        return 0


class FakeListItem:
    def __init__(self, data):
        self.data = data


class FakeListView:
    def __init__(self, items):
        self._items = items
        self.index = 0

    @property
    def children(self):
        return self._items

    @property
    def items(self):
        return self._items


def _make_app(option_mode="local"):
    app = MusicPlayerApp()
    app.mpv = FakeMPVPlayer()
    app.update_now_playing = lambda *a, **k: None
    app.query_one = lambda *a, **k: _raise()
    app.option_mode = option_mode
    return app


def _raise():
    raise RuntimeError("DOM access not allowed in this unit test")


def _navigator(shuffle=False, repeat="off", randrange=None):
    """Build a PlaylistNavigator whose app carries shuffle/repeat state."""
    app = SimpleNamespace(shuffle=shuffle, repeat=repeat)
    nav = PlaylistNavigator(app)
    if randrange is not None:
        nav._randrange = randrange
    return nav


# === _next_index pure logic ===================================================


def test_next_index_sequential_off_moves_forward():
    nav = _navigator()
    assert nav._next_index(0, 5, +1) == 1
    assert nav._next_index(3, 5, +1) == 4


def test_next_index_sequential_off_stops_at_end():
    nav = _navigator()
    assert nav._next_index(4, 5, +1) is None  # "off" -> no wrap


def test_next_index_sequential_off_stops_at_start():
    nav = _navigator()
    assert nav._next_index(0, 5, -1) is None


def test_next_index_repeat_all_wraps_forward_and_back():
    nav = _navigator(repeat="all")
    assert nav._next_index(4, 5, +1) == 0  # wrap to start
    assert nav._next_index(0, 5, -1) == 4  # wrap to end


def test_next_index_repeat_one_replays_current():
    nav = _navigator(repeat="one")
    assert nav._next_index(2, 5, +1) == 2
    assert nav._next_index(2, 5, -1) == 2


def test_next_index_shuffle_picks_different_item():
    nav = _navigator(shuffle=True, randrange=lambda n: 3 % n)
    # current=0; randrange(5)=3, different from 0 -> 3
    assert nav._next_index(0, 5, +1) == 3


def test_next_index_shuffle_never_equals_current():
    # Force randrange to always return 0; with current=1, 0 != 1 so it picks 0
    # (the loop guarantees a different value when count > 1).
    nav = _navigator(shuffle=True, randrange=lambda n: 0)
    assert nav._next_index(1, 4, +1) == 0


def test_next_index_shuffle_single_item_stays():
    nav = _navigator(shuffle=True)
    assert nav._next_index(0, 1, +1) == 0


def test_next_index_none_current_defaults_to_zero_then_advances():
    nav = _navigator()
    assert nav._next_index(None, 5, +1) == 1  # None -> 0, then +1


def test_next_index_empty_list_is_none():
    nav = _navigator()
    assert nav._next_index(0, 0, +1) is None


# === App actions ===============================================================


def test_toggle_shuffle_flips_state():
    app = _make_app()
    assert app.shuffle is False
    app.action_toggle_shuffle()
    assert app.shuffle is True
    app.action_toggle_shuffle()
    assert app.shuffle is False


def test_cycle_repeat_rotates_off_one_all():
    app = _make_app()
    assert app.repeat == "off"
    app.action_cycle_repeat()
    assert app.repeat == "one"
    app.action_cycle_repeat()
    assert app.repeat == "all"
    app.action_cycle_repeat()
    assert app.repeat == "off"


def test_toggle_shuffle_updates_nowplaying_indicator():
    app = _make_app()
    indicator = SimpleNamespace(shuffle=False, repeat="off")
    app.query_one = lambda *a, **k: indicator
    app.action_toggle_shuffle()
    assert indicator.shuffle is True


# === Integration with lists ===================================================


def _local_app():
    app = _make_app(option_mode="local")
    return app


def test_play_next_repeat_one_replays_same_local_index(tmp_path):
    app = _local_app()
    app.repeat = "one"
    # Create real temp files
    for i in range(4):
        mp3 = tmp_path / f"f{i}.mp3"
        mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    items = [FakeListItem({"source": str(tmp_path / f"f{i}.mp3"), "title": str(i)}) for i in range(4)]
    local_list = FakeListView(items)
    local_list.index = 1
    app.query_one = lambda *a, **k: local_list

    asyncio.run(app.playlist_navigator.play_next())
    assert app.mpv.calls[-1] == ("play", str(tmp_path / "f1.mp3"))
    assert local_list.index == 1


def test_play_next_repeat_all_wraps_local(tmp_path):
    app = _local_app()
    app.repeat = "all"
    # Create real temp files
    for i in range(3):
        mp3 = tmp_path / f"f{i}.mp3"
        mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    items = [FakeListItem({"source": str(tmp_path / f"f{i}.mp3"), "title": str(i)}) for i in range(3)]
    local_list = FakeListView(items)
    local_list.index = 2
    app.query_one = lambda *a, **k: local_list

    asyncio.run(app.playlist_navigator.play_next())
    assert app.mpv.calls[-1] == ("play", str(tmp_path / "f0.mp3"))
    assert local_list.index == 0


def test_play_next_sequential_off_stops_at_end_local():
    app = _local_app()
    app.repeat = "off"
    items = [FakeListItem({"source": f"/f{i}.mp3", "title": str(i)}) for i in range(3)]
    local_list = FakeListView(items)
    local_list.index = 2
    app.query_one = lambda *a, **k: local_list

    asyncio.run(app.playlist_navigator.play_next())
    assert ("play", "/f0.mp3") not in app.mpv.calls
    assert app.mpv.calls == []


def test_play_next_shuffle_picks_different_local(tmp_path):
    app = _local_app()
    app.shuffle = True
    app.repeat = "off"
    # Create real temp files
    for i in range(4):
        mp3 = tmp_path / f"f{i}.mp3"
        mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    items = [FakeListItem({"source": str(tmp_path / f"f{i}.mp3"), "title": str(i)}) for i in range(4)]
    local_list = FakeListView(items)
    local_list.index = 0
    app.query_one = lambda *a, **k: local_list
    # Deterministic: randrange(4) -> 2 (different from current 0).
    app.playlist_navigator._randrange = lambda n: 2

    asyncio.run(app.playlist_navigator.play_next())
    assert app.mpv.calls[-1] == ("play", str(tmp_path / "f2.mp3"))
    assert local_list.index == 2


def test_play_previous_sequential_off_stops_at_start_radio():
    app = _make_app(option_mode="radio")
    app.repeat = "off"
    app.stations = type(
        "S", (), {"stations": [{"name": f"R{i}", "url": f"http://r{i}"} for i in range(3)]}
    )()
    station_list = FakeListView([])
    station_list.index = 0
    app.query_one = lambda *a, **k: station_list

    asyncio.run(app.playlist_navigator.play_previous())
    # No-op at start: index unchanged.
    assert station_list.index == 0


def test_play_next_radio_repeat_all_wraps():
    app = _make_app(option_mode="radio")
    app.repeat = "all"
    station_objs = [{"name": f"R{i}", "url": f"http://r{i}"} for i in range(2)]

    class Stations:
        stations = station_objs

        def play(self, idx):
            return None

    app.stations = Stations()
    station_list = FakeListView([])
    station_list.index = 1
    app.query_one = lambda *a, **k: station_list

    asyncio.run(app.playlist_navigator.play_next())
    assert station_list.index == 0


def test_navigator_instantiated_on_app():
    app = _make_app()
    assert isinstance(app.playlist_navigator, PlaylistNavigator)
