"""Performance benchmarks for feature/13 metadata index.

Measures:
1. Cache lookup: individual get_track() calls (current baseline)
2. FTS search latency across large datasets
3. Widget mounting throughput

Run with: uv run pytest src/tests/test_feature_13_perf.py -v -s
"""

import asyncio
import time
from unittest.mock import MagicMock, patch

from textual.widgets import Static

from pytuiplayer.metadata_index import MetadataIndex
from pytuiplayer.playlist import PlaylistLoader
from pytuiplayer.tui_app import MusicPlayerApp


def _make_app_with_index(tmp_path, num_tracks=2000):
    """Create a MusicPlayerApp with a large FTS index."""
    app = MusicPlayerApp()
    app.mpv = MagicMock()

    db_path = tmp_path / "perf_test.db"
    app.metadata_index = MetadataIndex(db_path)

    tracks = [
        {
            "path": f"/music/artist{i % 100}/album{i % 50}/song{i}.mp3",
            "duration": 180.0 + (i % 120),
            "artist": f"Artist {i % 100}",
            "album": f"Album {i % 50}",
            "title": f"Song {i}",
            "track": (i % 12) + 1,
            "year": str(2000 + (i % 24)),
            "genre": ["Pop", "Rock", "Jazz", "Electronic", "Hip-Hop"][i % 5],
            "bitrate": 320000,
            "sample_rate": 44100,
            "channels": 2,
            "encoder": "LAME 3.99",
            "file_mtime": 1234567890.0 + i,
            "indexed_at": 1234567890.0 + i,
        }
        for i in range(num_tracks)
    ]
    app.metadata_index.store_batch(tracks)
    return app


class _FakeListView:
    def __init__(self):
        self.children = []
        self.index = None
        self._mount_count = 0

    async def mount(self, *items):
        self.children.extend(items)
        self._mount_count += 1

    async def remove_children(self):
        self.children.clear()

    def clear(self):
        self.children.clear()


class TestCacheLookupPerformance:
    """Benchmark cache lookup strategies."""

    def test_individual_get_track_2000(self, tmp_path):
        """Baseline: 2000 individual get_track() calls."""
        app = _make_app_with_index(tmp_path, 2000)
        paths = [f"/music/artist{i % 100}/album{i % 50}/song{i}.mp3" for i in range(2000)]

        start = time.perf_counter()
        results = [app.metadata_index.get_track(p) for p in paths]
        elapsed = time.perf_counter() - start

        assert len(results) == 2000
        print(f"\n[PERF] 2000 individual get_track(): {elapsed:.3f}s ({elapsed/2000*1000:.2f}ms each)")

    def test_bulk_get_tracks_2000(self, tmp_path):
        """Optimized: single get_tracks_bulk(paths) call."""
        app = _make_app_with_index(tmp_path, 2000)
        paths = [f"/music/artist{i % 100}/album{i % 50}/song{i}.mp3" for i in range(2000)]

        start = time.perf_counter()
        results = app.metadata_index.get_tracks_bulk(paths)
        elapsed = time.perf_counter() - start

        assert len(results) == 2000
        print(f"\n[PERF] get_tracks_bulk(2000 paths): {elapsed:.3f}s ({elapsed/2000*1000:.3f}ms each)")


class TestFTSSearchPerformance:
    """Benchmark FTS search latency."""

    def test_fts_search_2000(self, tmp_path):
        """FTS search across 2000 indexed tracks."""
        app = _make_app_with_index(tmp_path, 2000)

        queries = ["Artist 50", "Rock", "Song 1000", "Nonexistent"]
        for q in queries:
            start = time.perf_counter()
            results = app.metadata_index.search_tracks(q)
            elapsed = time.perf_counter() - start
            print(f"\n[PERF] FTS search '{q}': {elapsed*1000:.2f}ms ({len(results)} results)")


class TestEndToEndLoading:
    """End-to-end loading benchmarks."""

    def test_load_m3u_2000_cached(self, tmp_path):
        """Load 2000 M3U items when all are cached."""
        app = _make_app_with_index(tmp_path, 2000)

        m3u_path = tmp_path / "playlist.m3u"
        with open(m3u_path, "w") as f:
            f.write("#EXTM3U\n")
            for i in range(2000):
                f.write(f"#EXTINF:-1,Song {i}\n")
                f.write(f"/music/artist{i % 100}/album{i % 50}/song{i}.mp3\n")

        loader = PlaylistLoader(app)
        fake_lv = _FakeListView()

        def query_one_side_effect(selector, *args, **kwargs):
            if selector == "#local-list":
                return fake_lv
            if selector == "#loading-status":
                return MagicMock(spec=Static)
            return MagicMock()

        with patch.object(app, "query_one", side_effect=query_one_side_effect):
            start = time.perf_counter()
            asyncio.run(loader.load_m3u(m3u_path))
            elapsed = time.perf_counter() - start

        print(f"\n[PERF] load_m3u (2000 cached): {elapsed:.3f}s")
        print(f"  - Loaded: {len(fake_lv.children)} items")
        print(f"  - Mount calls: {fake_lv._mount_count}")
