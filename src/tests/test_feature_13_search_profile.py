"""Profile search flow step by step."""

import asyncio
import time
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from textual.widgets import Label, ListItem, ListView, Static

from pytuiplayer.metadata_index import MetadataIndex
from pytuiplayer.screens import LocalScreen
from pytuiplayer.tui_app import MusicPlayerApp
from pytuiplayer.types import ItemData


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


def _make_screen_with_2000(tmp_path):
    """Create a LocalScreen with 2000 items loaded."""
    app = MusicPlayerApp()
    app.mpv = MagicMock()

    db_path = tmp_path / "perf.db"
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
        for i in range(2000)
    ]
    app.metadata_index.store_batch(tracks)

    app.local_items = {}
    for t in tracks:
        item_data = ItemData(
            source=t["path"], title=t["title"], duration=t["duration"], meta=t["title"]
        )
        app.local_items[t["path"]] = item_data

    screen = LocalScreen()
    return screen, app


class TestSearchProfiling:
    """Profile each step of the search flow."""

    def test_profile_fts_search_only(self, tmp_path):
        """Profile FTS search alone."""
        screen, app = _make_screen_with_2000(tmp_path)

        queries = ["song", "artist", "rock", "song 1000", "xyz"]
        for q in queries:
            start = time.perf_counter()
            for _ in range(100):
                results = app.metadata_index.search_tracks(q)
            elapsed = time.perf_counter() - start
            print(f"\n[PERF] FTS search '{q}' x100: {elapsed*1000:.1f}ms ({elapsed*10:.2f}ms each, {len(results)} results)")

    def test_profile_resolve_search_results(self, tmp_path):
        """Profile _resolve_search_results (FTS + intersect)."""
        screen, app = _make_screen_with_2000(tmp_path)

        with patch.object(type(screen), "app", new_callable=PropertyMock, return_value=app):
            queries = ["song", "artist 50", "rock"]
            for q in queries:
                start = time.perf_counter()
                for _ in range(100):
                    results = screen._resolve_search_results(q, app.local_items)
                elapsed = time.perf_counter() - start
                print(f"\n[PERF] _resolve_search_results('{q}') x100: {elapsed*1000:.1f}ms ({elapsed*10:.2f}ms each, {len(results)} results)")

    def test_profile_widget_creation(self, tmp_path):
        """Profile widget creation loop."""
        screen, app = _make_screen_with_2000(tmp_path)

        with patch.object(type(screen), "app", new_callable=PropertyMock, return_value=app):
            start = time.perf_counter()
            count = 0
            for item_data in app.local_items.values():
                title = item_data.get("title", "")
                duration = item_data.get("duration")
                duration_str = f"{int(duration)//60:02d}:{int(duration)%60:02d}" if duration else ""
                display = f"{title:<40} {duration_str}"
                item = ListItem(Label(display))
                item.data = item_data
                count += 1
            elapsed = time.perf_counter() - start
            print(f"\n[PERF] Create {count} ListItem widgets: {elapsed*1000:.1f}ms ({elapsed/count*1000:.3f}ms each)")

    def test_profile_full_search_flow(self, tmp_path):
        """Profile the full _filter_local_list flow."""
        screen, app = _make_screen_with_2000(tmp_path)
        fake_lv = _FakeListView()

        # Pre-populate with 2000 items
        for item_data in app.local_items.values():
            item = ListItem(Label(f"{item_data['title']:<40} 03:20"))
            item.data = item_data
            fake_lv.children.append(item)

        with patch.object(type(screen), "app", new_callable=PropertyMock, return_value=app):
            queries = ["song", "artist 50", "rock", "xyz"]
            for q in queries:
                start = time.perf_counter()
                asyncio.run(screen._filter_local_list(fake_lv, q))
                elapsed = time.perf_counter() - start
                print(f"\n[PERF] Full _filter_local_list('{q}'): {elapsed*1000:.1f}ms ({len(fake_lv.children)} results, {fake_lv._mount_count} mounts)")

    def test_profile_remove_children(self, tmp_path):
        """Profile remove_children alone."""
        screen, app = _make_screen_with_2000(tmp_path)
        fake_lv = _FakeListView()

        # Pre-populate with 2000 items
        for item_data in app.local_items.values():
            item = ListItem(Label(f"{item_data['title']:<40} 03:20"))
            item.data = item_data
            fake_lv.children.append(item)

        start = time.perf_counter()
        for _ in range(100):
            fake_lv.children.clear()
        elapsed = time.perf_counter() - start
        print(f"\n[PERF] Clear 2000 children x100: {elapsed*1000:.1f}ms ({elapsed*10:.2f}ms each)")

    def test_profile_chunked_vs_bulk(self, tmp_path):
        """Compare chunked mounting vs bulk mounting."""
        screen, app = _make_screen_with_2000(tmp_path)

        # Build all widgets first
        all_items = list(app.local_items.values())
        widgets = []
        for item_data in all_items:
            title = item_data.get("title", "")
            duration = item_data.get("duration")
            duration_str = f"{int(duration)//60:02d}:{int(duration)%60:02d}" if duration else ""
            display = f"{title:<40} {duration_str}"
            item = ListItem(Label(display))
            item.data = item_data
            widgets.append(item)

        # Bulk mount
        fake_lv = _FakeListView()
        start = time.perf_counter()
        asyncio.run(fake_lv.mount(*widgets))
        bulk_time = time.perf_counter() - start
        print(f"\n[PERF] Bulk mount 2000 widgets: {bulk_time*1000:.1f}ms")

        # Chunked mount
        fake_lv2 = _FakeListView()
        start = time.perf_counter()
        batch_size = 50
        for i in range(0, len(widgets), batch_size):
            batch = widgets[i : i + batch_size]
            asyncio.run(fake_lv2.mount(*batch))
            asyncio.sleep(0)
        chunked_time = time.perf_counter() - start
        print(f"\n[PERF] Chunked mount 2000 widgets (50/batch): {chunked_time*1000:.1f}ms")
