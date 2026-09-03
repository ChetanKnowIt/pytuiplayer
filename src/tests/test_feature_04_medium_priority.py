"""Acceptance tests for feature/04-update-medium-priority.

Closes Medium Priority #1 — recursive directory scanning in `load_local_files`.
Follow-up medium items (search/filter, favorites, history, shuffle/repeat, configurable
bindings, export, album art) remain unscheduled and are tracked in ROADMAP.md.
"""

import asyncio
from pathlib import Path

from pytuiplayer.tui_app import MusicPlayerApp


# ---------------------------------------------------------------------------
# Shared fakes (same pattern as test_backlog_coverage.py / test_feature_02)
# ---------------------------------------------------------------------------
class FakeMPV:
    """In-memory mpv backend that records every call."""

    def __init__(self):
        self.calls = []
        self.player = None

    def play(self, source):
        self.calls.append(("play", source))

    def stop(self):
        self.calls.append("stop")


def _stub_app(app, mpv=None):
    """Build an app with no Textual DOM: fake mpv + stubbed UI hooks."""
    app.mpv = mpv or FakeMPV()
    app.update_now_playing = lambda *a, **k: None
    app.query_one = lambda *a, **k: (_ for _ in ()).throw(LookupError("no DOM"))
    return app


class FakeList:
    """List widget fake that captures mounted ListItems (mirrors load_local_files)."""

    def __init__(self):
        self.items = []
        self.index = None

    def clear(self):
        self.items.clear()

    def add_row(self, *values, key=None):
        self.items.append(values)

    def add_row(self, *values, key=None):
        self.items.append(values)


    async def mount(self, *items):
        self.items.extend(items)


def _make_app():
    app = _stub_app(MusicPlayerApp())
    # run_worker is a no-op so we don't spawn real Textual workers in unit tests
    app.run_worker = lambda *a, **k: None
    return app


def test_load_local_files_recursive(tmp_path):
    """load_local_files walks subdirectories and surfaces nested .mp3 files."""
    # Build a tree with nested music folders.
    (tmp_path / "a.mp3").write_text("")
    (tmp_path / "sub1").mkdir()
    (tmp_path / "sub1" / "b.mp3").write_text("")
    (tmp_path / "sub1" / "notes.txt").write_text("ignore me")
    (tmp_path / "sub1" / "sub2").mkdir()
    (tmp_path / "sub1" / "sub2" / "c.mp3").write_text("")
    (tmp_path / "sub1" / "sub2" / "deep").mkdir()
    (tmp_path / "sub1" / "sub2" / "deep" / "d.mp3").write_text("")

    app = _make_app()
    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    asyncio.run(app.load_local_files(tmp_path))

    # All 4 nested mp3s found (top-level + 3 levels deep); the .txt is ignored.
    assert len(fake.items) == 4
    sources = {item.data["source"] for item in fake.items}
    assert (tmp_path / "a.mp3") in sources
    assert (tmp_path / "sub1" / "b.mp3") in sources
    assert (tmp_path / "sub1" / "sub2" / "c.mp3") in sources
    assert (tmp_path / "sub1" / "sub2" / "deep" / "d.mp3") in sources
    # Every item emits the unified ItemData shape.
    for item in fake.items:
        assert item.data["title"].endswith(".mp3")
        assert item.data["duration"] is None


def test_load_local_files_recursive_respects_max_playlist_items(tmp_path):
    """A large nested tree is capped at max_playlist_items + batched mounting."""
    app = _make_app()
    app.max_playlist_items = 3
    app.playlist_batch_size = 2

    for i in range(5):
        d = tmp_path / f"dir{i}"
        d.mkdir()
        for j in range(3):
            (d / f"track_{i}_{j}.mp3").write_text("")

    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    asyncio.run(app.load_local_files(tmp_path))

    # Only the first 3 files are loaded (cap honored), even across directories.
    assert len(fake.items) == 3
    for item in fake.items:
        assert isinstance(item.data["source"], Path)


def test_load_local_files_recursive_batched_mounting(tmp_path):
    """Items are mounted in batches (playlist_batch_size), not one giant await."""
    app = _make_app()
    app.max_playlist_items = 50
    app.playlist_batch_size = 4

    for i in range(10):
        (tmp_path / f"t{i}.mp3").write_text("")

    # Capture the sizes of each mount batch.
    batches = []

    class RecordingList(FakeList):
        async def mount(self, *items):
            batches.append(len(items))
            self.items.extend(items)

    fake = RecordingList()
    app.query_one = lambda *a, **k: fake

    asyncio.run(app.load_local_files(tmp_path))

    assert len(fake.items) == 10
    # 10 items with batch_size 4 -> batches of [4, 4, 2]
    assert batches == [4, 4, 2]


def test_load_local_files_top_level_still_works(tmp_path):
    """Regression: a flat directory (no subdirs) behaves as before."""
    (tmp_path / "x.mp3").write_text("")
    (tmp_path / "y.mp3").write_text("")

    app = _make_app()
    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    asyncio.run(app.load_local_files(tmp_path))

    assert len(fake.items) == 2
    assert {item.data["source"] for item in fake.items} == {
        tmp_path / "x.mp3",
        tmp_path / "y.mp3",
    }


def test_switch_to_local_does_not_crash_on_fetch_duration_worker(tmp_path):
    """Regression: switching Radio -> Local must not crash the TUI.

    A previous bug passed the ListItem as run_worker's 2nd positional (the worker
    *name*), so fetch_duration ran with no `item` and raised TypeError; with
    exit_on_error=True (Textual default) the worker crashed the app. This test drives
    load_local_files with a recording run_worker and asserts the duration worker is
    invoked with the item bound and exit_on_error=False (no crash).
    """
    import asyncio

    app = _make_app()
    fake = FakeList()
    app.query_one = lambda *a, **k: fake

    # Provide at least one local mp3 so load_local_files actually spawns a worker.
    (tmp_path / "song.mp3").write_text("")

    # Monkeypatch run_worker to record the work and prove it is callable with the item
    # already bound (so fetch_duration(item) needs no extra positional args).
    captured = {}

    def recording_run_worker(work, *args, **kwargs):
        captured["work"] = work
        captured["kwargs"] = kwargs
        # Calling the bound work must not raise TypeError for a missing 'item' arg.
        coro = work()
        try:
            coro.close()
        except Exception:
            pass
        return None

    app.run_worker = recording_run_worker

    asyncio.run(app.load_local_files(tmp_path))

    assert captured.get("work") is not None
    # The partial already binds the item, so it is callable with zero extra args.
    assert len(captured["work"].args) == 1
    assert captured["kwargs"].get("exit_on_error") is False
