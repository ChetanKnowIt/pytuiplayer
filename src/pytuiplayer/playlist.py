"""Playlist loading and navigation for pytuiplayer.

Handles loading local MP3 files, M3U playlists, and prev/next navigation.
"""

import asyncio
import os
import random
import time
from functools import partial
from pathlib import Path

from mutagen import File as MutagenFile
from textual.widgets import Label, ListItem, ListView, Static

from pytuiplayer.logging_config import get_logger
from pytuiplayer.profiling import profile_async
from pytuiplayer.types import ItemData
from pytuiplayer.utils import fmt_mmss, parse_extinf, resolve_source

logger = get_logger("playlist")

# Optional – install with `pip install aiofiles`
try:
    import aiofiles
except Exception:  # pragma: no cover
    aiofiles = None


class PlaylistLoader:
    """Loads local MP3 files and M3U playlists into the local list."""

    def __init__(self, app):
        self.app = app

    @profile_async
    async def fetch_duration(self, item_data: dict) -> None:
        """Fetch the duration of a local MP3 and update its list item.

        Stores result in metadata cache for instant loading next time.
        Skips files marked as missing (path no longer exists).
        """
        if item_data.get("missing"):
            return

        src = item_data.get("source")
        if src is None:
            return
        if isinstance(src, str) and src.startswith(
            ("http://", "https://", "rtmp://", "ftp://")
        ):
            return
        try:
            src_path = Path(src)
        except (TypeError, ValueError):
            return

        try:
            audio = await asyncio.to_thread(MutagenFile, str(src_path))
            duration = int(audio.info.length) if audio and audio.info else None
        except Exception:
            logger.debug("mutagen read failed for %s", src_path, exc_info=True)
            duration = None

        item_data["duration"] = duration

        # Store in cache for instant loading next time
        if duration is not None and hasattr(self.app, 'metadata_index'):
            try:
                self.app.metadata_index.store_track({
                    "path": str(src_path),
                    "duration": duration,
                    "title": item_data.get("title") or src_path.name,
                    "indexed_at": time.time(),
                })
            except Exception:
                logger.debug("Failed to store duration in cache", exc_info=True)

        try:
            label_text = item_data.get("title") or (src_path.name if src_path else "")
            # Find the visible widget in the ListView and update its label
            local_list = self.app.query_one("#local-list", ListView)
            for child in local_list.children:
                if getattr(child, "data", None) is item_data:
                    child.query_one(Label).update(f"{label_text:<40} {fmt_mmss(duration)}")
                    break
        except Exception:
            logger.debug("label update failed (widget torn down)", exc_info=True)

    @profile_async
    async def load_local_files(self, path: Path):
        """Load all local MP3 files under path (recursively) into #local-list.

        Uses metadata cache for instant loading of previously-indexed files.
        Only uncached files will show '--:--' and trigger a background worker.
        Optimized:
        - Bulk cache lookup (1 SQL query) instead of N queries.
        - Skips "Loading..." message when all files are cached (instant display).
        """
        local_list = self.app.query_one("#local-list", ListView)
        local_list.index = None
        local_list.clear()
        self.app.local_items = {}

        max_items = self.app.max_playlist_items or float("inf")
        batch_size = min(50, self.app.playlist_batch_size)
        count = 0
        cached_count = 0

        # Phase 1: Walk directory and collect all MP3 paths (in thread for mounted drives)
        all_files: list[Path] = []
        try:
            def walk_dir():
                files = []
                for root, _dirs, filenames in os.walk(path):
                    for name in sorted(filenames):
                        if not name.lower().endswith(".mp3"):
                            continue
                        files.append(Path(root) / name)
                        if len(files) >= max_items:
                            return files
                return files
            all_files = await asyncio.to_thread(walk_dir)
        except Exception:
            logger.debug("Directory walk failed", exc_info=True)

        # Phase 2: Bulk cache lookup (single SQL query)
        cache_map: dict[str, dict] = {}
        if hasattr(self.app, "metadata_index") and all_files:
            try:
                paths_str = [str(f) for f in all_files]
                cached_tracks = self.app.metadata_index.get_tracks_bulk(paths_str)
                cache_map = {t["path"]: t for t in cached_tracks if t is not None}
            except Exception:
                logger.debug("Bulk cache lookup failed", exc_info=True)

        # Phase 3: Build widgets using cache map
        batch: list = []
        for file in all_files:
            item_data = ItemData(source=file, title=file.name, duration=None)

            # Check cache map for metadata
            cached = cache_map.get(str(file))
            if cached:
                item_data["duration"] = cached.get("duration")
                item_data["title"] = cached.get("title") or file.name
                item_data["meta"] = cached.get("title") or file.name
                cached_count += 1

            duration = item_data.get("duration")
            duration_str = fmt_mmss(duration) if duration is not None else "--:--"
            display = f"{item_data['title']:<40} {duration_str}"
            item = ListItem(Label(display))
            item.data = item_data
            batch.append(item)
            self.app.local_items[file] = item_data
            count += 1

            if len(batch) >= batch_size:
                await local_list.mount(*batch)
                batch.clear()
                await asyncio.sleep(0)

        if batch:
            await local_list.mount(*batch)
            batch.clear()

        # Phase 4: Show status only if some items need background work
        if cached_count == count:
            # All cached — no loading message needed, list is already rendered
            pass
        else:
            # Some uncached — show count, spawn background workers
            try:
                loading = self.app.query_one("#loading-status", Static)
                loading.update(f"✅ Loaded {count} tracks ({cached_count} cached)")
            except Exception:
                pass

        # Spawn workers only for uncached files
        for idx, item_data in enumerate(self.app.local_items.values()):
            if item_data.get("duration") is None:
                self.app.run_worker(
                    partial(self.fetch_duration, item_data),
                    name=f"fetch_duration:{idx}",
                    exit_on_error=False,
                )

    @profile_async
    async def load_m3u(self, path: Path):
        """Load a local M3U playlist into #local-list with cache integration.

        Optimized:
        - Bulk cache lookup (1 SQL query) instead of N queries.
        - Skips "Loading..." message when all items are cached (instant display).
        """
        local_list: ListView = self.app.query_one("#local-list", ListView)
        local_list.clear()
        self.app.local_items = {}

        base_dir = path.parent
        max_items = self.app.max_playlist_items or float("inf")
        batch_size = min(50, self.app.playlist_batch_size)

        # Parse all lines to data (in thread for mounted drives)
        items_data = []
        pending_meta: str | None = None
        pending_dur: int | None = None

        def parse_m3u():
            data = []
            pend_meta = None
            pend_dur = None
            with open(path, encoding="utf-8", errors="replace") as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith("#"):
                        if line.startswith("#EXTINF"):
                            pend_dur, pend_meta = parse_extinf(line)
                        continue

                    source = resolve_source(base_dir, line)
                    label = pend_meta or Path(source).name
                    duration = pend_dur

                    pend_meta = None
                    pend_dur = None

                    data.append((source, label, duration))
                    if len(data) >= max_items:
                        break
            return data

        try:
            items_data = await asyncio.to_thread(parse_m3u)
        except Exception:
            logger.debug("M3U parse failed", exc_info=True)

        # Build widgets with cache-aware logic (bulk lookup)
        batch = []
        cached_count = 0
        needs_worker_count = 0
        missing_count = 0

        # Bulk cache lookup: collect all sources that need lookup
        sources_to_lookup = [
            source for source, label, duration in items_data if duration is None
        ]
        cache_map: dict[str, dict] = {}
        if sources_to_lookup and hasattr(self.app, "metadata_index"):
            try:
                cached_tracks = self.app.metadata_index.get_tracks_bulk(sources_to_lookup)
                cache_map = {t["path"]: t for t in cached_tracks if t is not None}
            except Exception:
                logger.debug("Bulk cache lookup failed", exc_info=True)

        # Check file existence in background thread (avoids UI lock)
        local_sources = [
            (idx, source) for idx, (source, label, duration) in enumerate(items_data)
            if not source.startswith(("http://", "https://", "rtmp://", "ftp://"))
        ]
        missing_indices: set[int] = set()
        if local_sources:
            try:
                def check_files():
                    result = set()
                    for idx, src in local_sources:
                        if not Path(src).exists():
                            result.add(idx)
                    return result
                missing_indices = await asyncio.to_thread(check_files)
            except Exception:
                logger.debug("File existence check failed", exc_info=True)

        for idx, (source, label, duration) in enumerate(items_data):
            item_data = ItemData(
                source=source, title=label, duration=duration, meta=label
            )

            # Check cache map for existing metadata
            if item_data.get("duration") is None:
                cached = cache_map.get(source)
                if cached:
                    if cached.get("duration"):
                        item_data["duration"] = cached["duration"]
                        item_data["title"] = cached.get("title") or label
                        item_data["meta"] = cached.get("title") or label
                        cached_count += 1

            # Mark as missing if file doesn't exist
            if idx in missing_indices:
                item_data["missing"] = True
                missing_count += 1

            # Track if we need to spawn a worker for this item
            if item_data.get("duration") is None:
                needs_worker_count += 1

            self.app.local_items[source] = item_data

            duration_str = fmt_mmss(item_data.get("duration")) if item_data.get("duration") is not None else ""
            if item_data.get("missing"):
                display = f"{item_data['title']:<40} ⚠ {duration_str} (missing)"
            else:
                display = f"{item_data['title']:<40} {duration_str}"
            item = ListItem(Label(display))
            item.data = item_data
            item._meta_label = item_data['title']
            batch.append(item)

            if len(batch) >= batch_size:
                await local_list.mount(*batch)
                batch.clear()
                await asyncio.sleep(0)

        if batch:
            await local_list.mount(*batch)
            batch.clear()

        # Show status with missing file count
        if cached_count == len(items_data) and missing_count == 0:
            pass  # All cached, no missing
        else:
            try:
                loading = self.app.query_one("#loading-status", Static)
                parts = []
                if cached_count > 0:
                    parts.append(f"{cached_count} cached")
                if missing_count > 0:
                    parts.append(f"{missing_count} missing")
                status = ", ".join(parts) if parts else f"{len(items_data)} tracks"
                loading.update(f"✅ Loaded {len(items_data)} tracks ({status})")
            except Exception:
                pass

        # Spawn duration workers only for items without duration
        for idx, item_data in enumerate(self.app.local_items.values()):
            if item_data.get("duration") is None:
                self.app.run_worker(
                    partial(self.fetch_duration, item_data),
                    name=f"fetch_duration:{idx}",
                    exit_on_error=False,
                )

    async def _populate_missing_durations(self, list_view: ListView):
        """Walk already-mounted items and fill missing durations from file tags."""
        for item in list_view.children:
            data = getattr(item, "data", None)
            if not isinstance(data, dict):
                continue
            if data.get("duration") is not None:
                continue

            src = data.get("source")
            if src is None:
                continue
            if isinstance(src, str) and src.startswith(
                ("http://", "https://", "rtmp://", "ftp://")
            ):
                continue
            try:
                src_path = Path(src)
            except (TypeError, ValueError):
                continue
            if not src_path.exists():
                continue

            try:
                audio = await asyncio.to_thread(MutagenFile, src_path, easy=True)
                dur = int(audio.info.length) if audio and audio.info else None
                if dur is not None:
                    data["duration"] = dur
                    label_text = data.get("meta") or data.get("title") or src_path.name
                    label = item.query_one(Label)
                    label.update(f"{label_text:<40} {fmt_mmss(dur)}")
            except Exception:
                logger.debug("duration fill failed for %s", src_path, exc_info=True)


class PlaylistNavigator:
    """Handles prev/next navigation in local and radio lists.

    Honors the app's shuffle / repeat state:
      - ``shuffle``  -> next/prev pick a random different item
      - ``repeat``   -> "one" replays current; "all" wraps at the ends;
                        "off" stops at the first/last item.
    """

    def __init__(self, app):
        self.app = app
        self._randrange = random.randrange

    @profile_async
    async def play_previous(self):
        """Play the previous track in the current list."""
        if self.app.option_mode == "local":
            await self._play_adjacent_local(-1)
        elif self.app.option_mode == "radio":
            await self._play_adjacent_radio(-1)

    @profile_async
    async def play_next(self):
        """Play the next track in the current list."""
        if self.app.option_mode == "local":
            await self._play_adjacent_local(1)
        elif self.app.option_mode == "radio":
            await self._play_adjacent_radio(1)

    def _next_index(self, current: int | None, count: int, direction: int) -> int | None:
        """Compute the index to play given shuffle/repeat state.

        Returns ``None`` when navigation should be a no-op (e.g. "off" repeat
        at the first/last item). ``direction`` is +1 for next, -1 for previous.
        """
        if count <= 0:
            return None
        if current is None:
            current = 0

        repeat = getattr(self.app, "repeat", "off")
        if repeat == "one":
            # Replay the current item regardless of direction.
            return current

        if getattr(self.app, "shuffle", False):
            if count == 1:
                return 0
            pick = current
            # Pick a different item at random (no infinite loop: count > 1).
            while pick == current:
                pick = self._randrange(count)
            return pick

        # Sequential (shuffle off).
        new = current + direction
        if new < 0:
            if repeat == "all":
                return count - 1
            return None  # stop at start
        if new >= count:
            if repeat == "all":
                return 0
            return None  # stop at end
        return new

    @profile_async
    async def _play_adjacent_local(self, direction: int):
        """Navigate to adjacent track in local list (honoring shuffle/repeat)."""
        try:
            local_list = self.app.query_one("#local-list", ListView)
            items = self.app._resolve_playlist_items(local_list)
            count = len(items)
            if count == 0:
                return

            new_index = self._next_index(local_list.index, count, direction)
            if new_index is None:
                return

            item = items[new_index]
            data = getattr(item, "data", None)
            if isinstance(data, dict):
                self.app.play_local(data)
                local_list.index = new_index
        except Exception:
            logger.debug("play adjacent local failed", exc_info=True)

    @profile_async
    async def _play_adjacent_radio(self, direction: int):
        """Navigate to adjacent station in radio list (honoring shuffle/repeat)."""
        try:
            station_list = self.app.query_one("#station-list", ListView)
            if not self.app.stations or not self.app.stations.stations:
                return

            count = len(self.app.stations.stations)
            new_index = self._next_index(station_list.index, count, direction)
            if new_index is None:
                return

            station = self.app.stations.stations[new_index]
            await self.app.play_station(station, new_index)
            station_list.index = new_index
        except Exception:
            logger.debug("play adjacent radio failed", exc_info=True)
