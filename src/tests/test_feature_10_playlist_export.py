"""feature/10 acceptance tests — playlist export to M3U (ROADMAP Low Priority #6).

Covers PlaylistExporter (build_lines / export_m3u) plus the app-level export
action. Pure file I/O — no Textual DOM or live mpv required.

Pattern: inject ``FakeMPVPlayer`` via ``app.mpv = ...``, stub ``query_one`` and
``update_now_playing`` to avoid the DOM, and drive the methods directly.
"""


from pytuiplayer.exporter import PlaylistExporter
from pytuiplayer.tui_app import MusicPlayerApp


class FakeMPVPlayer:
    def pause(self):
        pass

    def unpause(self):
        pass

    def stop(self):
        pass

    def play(self, source):
        pass

    def is_paused(self):
        return True

    def set_volume(self, volume):
        pass

    def get_time_pos(self):
        return 0

    def get_duration(self):
        return 0


def _make_app():
    app = MusicPlayerApp()
    app.mpv = FakeMPVPlayer()
    app.update_now_playing = lambda *a, **k: None
    app.query_one = lambda *a, **k: _raise()
    return app


def _raise():
    raise RuntimeError("DOM access not allowed in this unit test")


SAMPLE_ITEMS = [
    {"source": "/music/a.mp3", "title": "Song A", "duration": 210, "meta": "Song A"},
    {"source": "/music/b.mp3", "title": "Song B", "duration": None, "meta": "Song B"},
    {"source": "http://stream/radio.m3u", "title": "Web Radio", "duration": -1, "meta": "Web Radio"},
]


def test_build_lines_emits_extm3u_and_extinf():
    exp = PlaylistExporter(None)
    lines = exp.build_lines(SAMPLE_ITEMS)
    assert lines[0] == "#EXTM3U"
    # Three entries -> 1 header + 3*(EXTINF + path) = 7 lines
    assert len(lines) == 7
    assert lines[1] == "#EXTINF:210,Song A"
    assert lines[2] == "/music/a.mp3"
    assert lines[3] == "#EXTINF:-1,Song B"  # unknown duration -> -1
    assert lines[4] == "/music/b.mp3"
    assert lines[5] == "#EXTINF:-1,Web Radio"
    assert lines[6] == "http://stream/radio.m3u"


def test_build_lines_skips_items_without_source():
    exp = PlaylistExporter(None)
    items = [{"title": "No source", "duration": 10}, {"source": "/ok.mp3", "title": "Ok", "duration": 5}]
    lines = exp.build_lines(items)
    # header + 1 valid entry (EXTINF + path)
    assert lines == ["#EXTM3U", "#EXTINF:5,Ok", "/ok.mp3"]


def test_build_lines_falls_back_to_filename_for_title():
    exp = PlaylistExporter(None)
    lines = exp.build_lines([{"source": "/music/unknown.mp3", "duration": 100}])
    assert lines[1] == "#EXTINF:100,unknown.mp3"


def test_export_m3u_writes_file(tmp_path):
    exp = PlaylistExporter(None)
    out = tmp_path / "out.m3u"
    written = exp.export_m3u(out, SAMPLE_ITEMS)
    assert written == out
    text = out.read_text(encoding="utf-8")
    assert text.startswith("#EXTM3U\n")
    assert "#EXTINF:210,Song A" in text
    assert "/music/a.mp3" in text
    assert text.endswith("\n")


def test_export_m3u_creates_parent_dirs(tmp_path):
    exp = PlaylistExporter(None)
    out = tmp_path / "nested" / "dir" / "playlist.m3u"
    exp.export_m3u(out, SAMPLE_ITEMS)
    assert out.exists()


def test_export_m3u_empty_items_writes_header_only(tmp_path):
    exp = PlaylistExporter(None)
    out = tmp_path / "empty.m3u"
    exp.export_m3u(out, [])
    assert out.read_text(encoding="utf-8") == "#EXTM3U\n"


def test_app_export_playlist_to_writes_local_items(tmp_path):
    app = _make_app()
    app.local_items = {
        "/music/a.mp3": {"source": "/music/a.mp3", "title": "Song A", "duration": 210},
        "/music/b.mp3": {"source": "/music/b.mp3", "title": "Song B", "duration": None},
    }
    out = tmp_path / "exported.m3u"
    result = app.export_playlist_to(out)
    assert result == out
    text = out.read_text(encoding="utf-8")
    assert "#EXTINF:210,Song A" in text
    assert "#EXTINF:-1,Song B" in text


def test_app_export_playlist_action_no_items_shows_warning():
    app = _make_app()
    app.local_items = {}
    captured = {}
    app.update_now_playing = lambda *a, **k: captured.update(
        zip(("t", "s", "st"), a, strict=False)
    )
    app.action_export_playlist()
    assert captured.get("t") == "Nothing to export"


def test_app_export_playlist_action_exports(tmp_path, monkeypatch):
    app = _make_app()
    app.local_items = {
        "/music/a.mp3": {"source": "/music/a.mp3", "title": "Song A", "duration": 100},
    }
    # Redirect default path into tmp.
    monkeypatch.setenv("HOME", str(tmp_path))
    app.action_export_playlist()
    # default_export_path -> ~/Music/pytuiplayer/playlist.m3u
    out = tmp_path / "Music" / "pytuiplayer" / "playlist.m3u"
    assert out.exists()
    assert "#EXTINF:100,Song A" in out.read_text(encoding="utf-8")


def test_exporter_instantiated_on_app():
    app = _make_app()
    assert isinstance(app.playlist_exporter, PlaylistExporter)
