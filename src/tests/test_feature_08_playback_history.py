"""feature/08 acceptance tests — playback history tracking (ROADMAP Low Priority #3).

Covers the HistoryTracker controller plus its integration with
``play_station`` / ``play_local`` and the replay action.

Pattern: inject ``FakeMPVPlayer`` via ``app.mpv = ...``, stub ``query_one``
and ``update_now_playing`` to avoid the Textual DOM, and call the app methods
directly (no live mpv / network).
"""

import asyncio
from pathlib import Path

from pytuiplayer.history import HistoryTracker
from pytuiplayer.tui_app import MusicPlayerApp


class FakeMPVPlayer:
    """Minimal fake mpv player for unit testing (no real audio)."""

    def __init__(self):
        self.paused = True
        self.calls = []
        self.path = None

    def pause(self):
        self.paused = True
        self.calls.append("pause")

    def unpause(self):
        self.paused = False
        self.calls.append("unpause")

    def stop(self):
        self.calls.append("stop")

    def play(self, source):
        self.path = source
        self.calls.append(("play", source))

    def is_paused(self):
        return self.paused

    def set_volume(self, volume):
        self.calls.append(("set_volume", volume))

    def get_time_pos(self):
        return 0

    def get_duration(self):
        return 0


def _make_app():
    app = MusicPlayerApp()
    app.mpv = FakeMPVPlayer()
    app.update_now_playing = lambda *a, **k: None
    # Avoid touching the Textual DOM / screen stack in unit tests.
    app.query_one = lambda *a, **k: _raise()
    return app


class _DomSentinel:
    """Raised by the stubbed query_one so DOM access in tests is visibly caught."""


def _raise():
    raise RuntimeError("DOM access not allowed in this unit test")


# === HistoryTracker unit tests ================================================


def test_history_record_and_recent_order():
    tracker = HistoryTracker(None)
    tracker.record("radio", "Station A", "http://a")
    tracker.record("radio", "Station B", "http://b")
    tracker.record("local", "Song C", "/music/c.mp3")

    recent = tracker.recent()
    assert len(recent) == 3
    # Most-recent-first ordering.
    assert recent[0] == {"mode": "local", "title": "Song C", "source": "/music/c.mp3"}
    assert recent[1] == {"mode": "radio", "title": "Station B", "source": "http://b"}
    assert recent[2] == {"mode": "radio", "title": "Station A", "source": "http://a"}


def test_history_dedupes_consecutive_repeats():
    tracker = HistoryTracker(None)
    tracker.record("radio", "Station A", "http://a")
    tracker.record("radio", "Station A", "http://a")  # identical -> ignored
    tracker.record("radio", "Station A", "http://a")  # identical -> ignored
    assert tracker.count == 1


def test_history_is_not_deduped_across_non_consecutive():
    tracker = HistoryTracker(None)
    tracker.record("radio", "A", "http://a")
    tracker.record("radio", "B", "http://b")
    tracker.record("radio", "A", "http://a")  # re-play after B -> kept
    assert tracker.count == 3


def test_history_recent_limits_to_n():
    tracker = HistoryTracker(None)
    for i in range(5):
        tracker.record("radio", f"S{i}", f"http://s{i}")
    assert len(tracker.recent(3)) == 3
    assert len(tracker.recent()) == 5


def test_history_caps_at_max_items():
    tracker = HistoryTracker(None, max_items=3)
    for i in range(10):
        tracker.record("radio", f"S{i}", f"http://s{i}")
    assert tracker.count == 3
    # Only the last 3 played remain, most-recent first.
    assert [e["title"] for e in tracker.recent()] == ["S9", "S8", "S7"]


def test_history_ignores_empty_title_or_source():
    tracker = HistoryTracker(None)
    tracker.record("radio", "", "http://a")
    tracker.record("radio", "A", "")
    assert tracker.count == 0


def test_history_replay_returns_entry_or_none():
    tracker = HistoryTracker(None)
    tracker.record("local", "Song", "/x.mp3")
    assert tracker.replay(0)["source"] == "/x.mp3"
    assert tracker.replay(5) is None
    assert tracker.replay(-1) is None


def test_history_clear():
    tracker = HistoryTracker(None)
    tracker.record("radio", "A", "http://a")
    tracker.clear()
    assert tracker.count == 0


# === App integration tests =====================================================


def test_play_station_records_history():
    app = _make_app()
    app.stations = type(
        "S", (), {"stations": [{"name": "One", "url": "http://one"}]}
    )()
    app.stations.play = lambda idx: None  # no-op; mpv.play via player

    asyncio.run(app.play_station({"name": "One", "url": "http://one"}, 0))
    recent = app.recent_history()
    assert len(recent) == 1
    assert recent[0]["mode"] == "radio"
    assert recent[0]["title"] == "One"
    assert recent[0]["source"] == "http://one"


def test_play_local_filesystem_records_history(tmp_path):
    app = _make_app()
    mp3 = tmp_path / "song.mp3"
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    app.play_local(mp3)
    recent = app.recent_history()
    assert len(recent) == 1
    assert recent[0]["mode"] == "local"
    assert recent[0]["source"] == str(mp3.resolve()) or recent[0]["source"].endswith("song.mp3")


def test_play_local_url_records_history_as_local_mode():
    app = _make_app()
    app.play_local({"source": "http://stream/radio.mp3", "meta": "Web Radio"})
    recent = app.recent_history()
    assert len(recent) == 1
    assert recent[0]["mode"] == "local"  # URL entry in local list stays "local"
    assert recent[0]["title"] == "Web Radio"
    assert recent[0]["source"] == "http://stream/radio.mp3"


def test_history_interleaved_radio_and_local(tmp_path):
    app = _make_app()
    app.stations = type(
        "S", (), {"stations": [{"name": "RR", "url": "http://rr"}]}
    )()
    app.stations.play = lambda idx: None

    mp3_a = tmp_path / "a.mp3"
    mp3_a.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    mp3_b = tmp_path / "b.mp3"
    mp3_b.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)

    app.play_local(mp3_a)
    asyncio.run(app.play_station({"name": "RR", "url": "http://rr"}, 0))
    app.play_local(mp3_b)

    recent = app.recent_history()
    assert [e["title"] for e in recent] == ["b", "RR", "a"]
    assert [e["mode"] for e in recent] == ["local", "radio", "local"]


def test_action_play_history_last_replays_local(tmp_path):
    app = _make_app()
    mp3 = tmp_path / "again.mp3"
    mp3.write_bytes(b"\xff\xfb\x90\x00" + b"\x00" * 100)
    app.play_local(mp3)

    # Stub replay target so we don't need a real mpv path resolution.
    app.mpv.play = lambda src: setattr(app, "_replayed", src)
    app.action_play_history_last()
    assert getattr(app, "_replayed", None).endswith("again.mp3")


def test_action_play_history_last_no_history_shows_warning():
    app = _make_app()
    # recent_history stubbed to empty
    captured = {}
    app.update_now_playing = lambda *a, **k: captured.update(
        zip(("t", "s", "st"), a, strict=False)
    )
    app.action_play_history_last()
    assert captured.get("t") == "No history yet"


def test_history_tracker_instantiated_on_app():
    app = _make_app()
    assert isinstance(app.history_tracker, HistoryTracker)
