"""Playlist loading and navigation for pytuiplayer.

Handles loading local MP3 files, M3U playlists, and prev/next navigation.
"""

import asyncio
import os
from collections.abc import AsyncIterator
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
        """Fetch the duration of a local MP3 and update its list item."""
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
            audio = MutagenFile(str(src_path))
            duration = int(audio.info.length) if audio and audio.info else None
        except Exception:
            logger.debug("mutagen read failed for %s", src_path, exc_info=True)
            duration = None

        item_data["duration"] = duration
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
        """Load all local MP3 files under path (recursively) into #local-list."""
        local_list = self.app.query_one("#local-list", ListView)
        local_list.index = None
        local_list.clear()
        self.app.local_items = {}

        max_items = self.app.max_playlist_items or float("inf")
        batch_size = self.app.playlist_batch_size
        batch: list = []
        count = 0

        try:
            loading = self.app.query_one("#loading-status", Static)
            loading.update("📂 Scanning for MP3 files...")
        except Exception:
            loading = None

        for root, _dirs, files in os.walk(path):
            for name in sorted(files):
                if not name.lower().endswith(".mp3"):
                    continue

                file = Path(root) / name
                item = ListItem(Label(f"{file.name:<40} --:--"))
                item.data = ItemData(source=file, title=file.name, duration=None)
                batch.append(item)
                # Store the data dict (not widget) so _filter_local_list can rebuild
                self.app.local_items[file] = item.data
                count += 1

                if len(batch) >= batch_size:
                    await local_list.mount(*batch)
                    batch.clear()
                    if loading:
                        loading.update(f"📂 Scanning... ({count} files found)")
                    await asyncio.sleep(0)

                if count >= max_items:
                    if batch:
                        await local_list.mount(*batch)
                        batch.clear()
                    break
            else:
                continue
            break

        if batch:
            await local_list.mount(*batch)
            batch.clear()

        if loading:
            loading.update(f"✅ Loaded {count} tracks")
        for idx, item in enumerate(self.app.local_items.values()):
            self.app.run_worker(
                partial(self.fetch_duration, item),
                name=f"fetch_duration:{idx}",
                exit_on_error=False,
            )

    @profile_async
    async def load_m3u(self, path: Path):
        """Load a local M3U playlist into #local-list in batches."""
        local_list: ListView = self.app.query_one("#local-list", ListView)
        local_list.clear()
        self.app.local_items = {}

        base_dir = path.parent
        max_items = self.app.max_playlist_items or float("inf")
        batch_size = self.app.playlist_batch_size

        try:
            loading = self.app.query_one("#loading-status", Static)
            loading.update("📂 Loading playlist...")
        except Exception:
            loading = None

        async def line_generator() -> AsyncIterator[str]:
            if aiofiles:
                async with aiofiles.open(
                    path, mode="r", encoding="utf-8", errors="replace"
                ) as f:
                    async for raw in f:
                        line = raw.strip()
                        if line:
                            yield line
            else:
                with open(path, encoding="utf-8", errors="replace") as f:
                    for raw in f:
                        line = raw.strip()
                        if line:
                            yield line

        batch: list = []
        pending_meta: str | None = None
        pending_dur: int | None = None
        count = 0

        async for line in line_generator():
            if line.startswith("#EXTINF"):
                pending_dur, pending_meta = parse_extinf(line)
                continue

            if line.startswith("#"):
                continue

            source = resolve_source(base_dir, line)
            label = pending_meta or Path(source).name
            duration = pending_dur

            pending_meta = None
            pending_dur = None

            duration_str = fmt_mmss(duration) if duration is not None else ""
            display = f"{label:<40} {duration_str}"
            item = ListItem(Label(display))
            item.data = ItemData(
                source=source,
                title=label,
                duration=duration,
                meta=label,
            )
            item._meta_label = label

            batch.append(item)
            # Store the data dict (not the widget) so _filter_local_list can rebuild
            # fresh ListItems from it. Widgets can't be reused after clear()+mount().
            self.app.local_items[source] = item.data
            count += 1

            if count >= max_items:
                break

            if len(batch) >= batch_size:
                await local_list.mount(*batch)
                batch.clear()
                if loading:
                    loading.update(f"📂 Loading playlist... ({count} items)")
                if count % 100 == 0:
                    await asyncio.sleep(0)

        await local_list.mount(*batch)
        batch.clear()

        if self.app.fetch_duration_eager:
            asyncio.create_task(self._populate_missing_durations(local_list))

        if loading:
            loading.update(f"✅ Loaded {count} tracks")

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
    """Handles prev/next navigation in local and radio lists."""

    def __init__(self, app):
        self.app = app

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

    @profile_async
    async def _play_adjacent_local(self, direction: int):
        """Navigate to adjacent track in local list."""
        try:
            local_list = self.app.query_one("#local-list", ListView)
            if local_list.index is None:
                new_index = 0
            else:
                new_index = local_list.index + direction

            items = self.app._resolve_playlist_items(local_list)
            if items and 0 <= new_index < len(items):
                item = items[new_index]
                data = getattr(item, "data", None)
                if isinstance(data, dict):
                    self.app.play_local(data)
                    local_list.index = new_index
        except Exception:
            logger.debug("play adjacent local failed", exc_info=True)

    @profile_async
    async def _play_adjacent_radio(self, direction: int):
        """Navigate to adjacent station in radio list."""
        try:
            station_list = self.app.query_one("#station-list", ListView)
            if not self.app.stations or not self.app.stations.stations:
                return

            if station_list.index is None:
                new_index = 0
            else:
                new_index = station_list.index + direction

            if 0 <= new_index < len(self.app.stations.stations):
                station = self.app.stations.stations[new_index]
                await self.app.play_station(station, new_index)
                station_list.index = new_index
        except Exception:
            logger.debug("play adjacent radio failed", exc_info=True)
