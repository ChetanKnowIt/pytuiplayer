"""Main Textual app for pytuiplayer.

Thin orchestrator: business logic lives here, but widgets, screens,
constants, and helpers are imported from their own modules.
"""

import asyncio
import json
import os
import traceback
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

# Optional – install with `pip install aiofiles`
try:
    import aiofiles
except Exception:  # pragma: no cover
    aiofiles = None  # fallback to sync reading (still faster than the original)

from anyio import open_file  # <- a coroutine
from mutagen import File as MutagenFile
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Label,
    ListItem,
    ListView,
)

from pytuiplayer.constants import (
    DEFAULT_PLAYLIST_BATCH_SIZE,
    ICON_ERR,
    MAX_PLAYLIST_ITEMS,
)
from pytuiplayer.logging_config import get_logger, setup_logging
from pytuiplayer.mpv_player import MPVPlayer
from pytuiplayer.profiling import profile, profile_async
from pytuiplayer.screens import LocalScreen, RadioScreen
from pytuiplayer.station_player import StationPlayer
from pytuiplayer.types import ItemData
from pytuiplayer.utils import fmt_mmss, parse_extinf, resolve_source
from pytuiplayer.widgets import NowPlaying, NowPlayingMessage, ProgressBar, VolumeIndicator

logger = get_logger("tui_app")


class MusicPlayerApp(App):
    """Terminal music player with radio and local playback modes.

    Mode switching uses Textual's screen stack (``RadioScreen`` /
    ``LocalScreen``) instead of manual visibility toggling.
    """

    CSS_PATH = "musicplayer_tui.css"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding("space", action="toggle_play", description="Play/Pause"),
        Binding("p", "play", description="Play"),
        Binding("k", "pause", description="Pause"),
        Binding("s", "stop", "Stop"),
        Binding("h", "seek_backward", "Seek -5s"),
        Binding("l", "seek_forward", "Seek +5s"),
        Binding("1", "seek_to_10", description="Seek to 10%"),
        Binding("5", "seek_to_50", description="Seek to 50%"),
        Binding("9", "seek_to_90", description="Seek to 90%"),
        Binding("+", "volume_up", description="Volume +"),
        Binding("-", "volume_down", description="Volume -"),
        Binding("m", "toggle_mute", description="Mute toggle"),
        Binding("o", "play_playlist", description="Play playlist from start"),
    ]

    def query_one(self, selector, *args, **kwargs):
        """Delegate query to the active screen so widgets inside pushed screens are found."""
        try:
            return self.screen.query_one(selector, *args, **kwargs)
        except Exception:
            return super().query_one(selector, *args, **kwargs)

    def __init__(self):
        super().__init__()
        self.mpv = MPVPlayer()
        self.stations = None
        self.currently_playing = None
        self._stream_source = False  # True when a network stream (radio/M3U URL) is playing
        self.option_mode = "radio"  # default
        self.stations_file = Path(__file__).parent / "stations.json"
        self.current_title = "Nothing playing"

        # Volume state
        self.volume = 50
        self.muted = False
        self._prev_volume = self.volume

        # Playlist loading controls (can be overridden in tests or by callers)
        self.max_playlist_items = MAX_PLAYLIST_ITEMS
        self.playlist_batch_size = DEFAULT_PLAYLIST_BATCH_SIZE
        self.fetch_duration_eager = False  # set True for eager duration fetch at load

        # Local-file metadata polling state (see _refresh_local_metadata)
        self._current_local_source = None
        self._local_meta_source = None

    # Maximum number of playlist items to load by default (safety for very large M3U files)
    MAX_PLAYLIST_ITEMS = MAX_PLAYLIST_ITEMS

    def compose(self) -> ComposeResult:
        """Compose is handled by the active screen."""
        yield Header()
        yield Footer()

    @profile_async
    async def on_mount(self) -> None:
        setup_logging()
        logger.info("Application mounted")
        self.title = "Music Player"
        # initialize player volume
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            logger.debug("set_volume failed on mount", exc_info=True)
        # progress update and metadata polling
        self.set_interval(0.5, self.update_progress)
        self.set_interval(1.0, self._refresh_metadata)

        # Start in radio mode via screen abstraction
        self.push_screen(RadioScreen())

    @profile
    def update_volume_ui(self):
        try:
            vol = self.query_one("#volume-indicator", VolumeIndicator)
            vol.volume = self.volume
            vol.muted = self.muted
        except Exception:
            logger.debug("update_volume_ui failed", exc_info=True)

    @profile
    def action_volume_up(self):
        self.volume = min(100, getattr(self, "volume", 50) + 5)
        if self.muted:
            self.muted = False
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            logger.warning("set_volume failed", exc_info=True)
        self.update_volume_ui()

    @profile
    def action_volume_down(self):
        self.volume = max(0, getattr(self, "volume", 50) - 5)
        if self.volume == 0:
            self.muted = True
        else:
            self.muted = False
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            logger.warning("set_volume failed", exc_info=True)
        self.update_volume_ui()

    @profile
    def action_toggle_mute(self):
        if not getattr(self, "muted", False):
            self._prev_volume = getattr(self, "volume", 50)
            self.muted = True
            try:
                self.mpv.set_volume(0)
            except Exception:
                logger.warning("set_volume(0) failed", exc_info=True)
        else:
            self.muted = False
            self.volume = getattr(self, "_prev_volume", 50)
            try:
                self.mpv.set_volume(self.volume)
            except Exception:
                logger.warning("set_volume failed", exc_info=True)
        self.update_volume_ui()

    async def fetch_duration(self, item: ListItem) -> None:
        """Fetch the duration of a local MP3 and update its list item.

        This is a plain coroutine that runs off the main thread when launched via
        ``self.run_worker(self.fetch_duration, item)`` from ``load_local_files``
        (the correct Textual worker entry point). It resolves the item's ``source``
        ``Path``/string, reads the tag with mutagen, stores the duration in
        ``item.data['duration']``, and refreshes the visible label.
        """
        data = getattr(item, "data", None)
        if not isinstance(data, dict):
            return
        src = data.get("source")
        if src is None:
            return
        # Skip radio/stream URLs – duration is not available from local tags.
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

        data["duration"] = duration
        try:
            label_text = data.get("title") or (src_path.name if src_path else "")
            self.call_from_thread(
                item.query_one(Label).update,
                f"{label_text:<40} {fmt_mmss(duration)}",
            )
        except Exception:
            # Widget may have been torn down; nothing to update.
            logger.debug("label update failed (widget torn down)", exc_info=True)

    @profile_async
    async def on_radio_set_changed(self, event):
        """Handle mode switch via screen abstraction."""
        radio = event.pressed.id == "radio-option"
        new_mode = "radio" if radio else "local"

        if self.option_mode != new_mode:
            self.mpv.stop()
            self.current_title = "Nothing playing"
            self.update_now_playing("Nothing playing", "", "⏹")

        self.option_mode = new_mode

        # Switch screens instead of toggling visibility (defensive: screen stack
        # may not exist in unit tests that bypass the full Textual lifecycle)
        try:
            current = self.screen
            if radio:
                if not isinstance(current, RadioScreen):
                    self.switch_screen(RadioScreen())
            else:
                if not isinstance(current, LocalScreen):
                    self.switch_screen(LocalScreen())
        except Exception:
            logger.debug("Screen switch failed (no screen stack?)", exc_info=True)

    @profile_async
    async def load_local_files(self, path: Path):
        local_list = self.query_one("#local-list", ListView)
        local_list.index = None  # prevent index tracking
        local_list.clear()
        self.local_items = {}  # keep a mapping for easy update

        for file in path.iterdir():
            if file.suffix.lower() != ".mp3":
                continue

            item = ListItem(Label(f"{file.name:<40} --:--"))
            item.data = ItemData(source=file, title=file.name, duration=None)
            await local_list.mount(item)
            self.local_items[file] = item

            # Fire-and-forget: fetch duration in background (Textual worker)
            self.run_worker(self.fetch_duration, item)

    @profile_async
    async def load_m3u(self, path: Path):
        """Load a local M3U playlist into ``#local-list`` in batches.

        * Supports ``#EXTINF`` metadata lines and resolves relative paths.
        * Yields to the event-loop between batches so the UI stays responsive.
        * Honors ``self.max_playlist_items``.
        * (Optional) fetches song duration lazily – see ``self.fetch_duration``.
        """
        local_list: ListView = self.query_one("#local-list", ListView)
        local_list.clear()

        base_dir = path.parent
        max_items = self.max_playlist_items or float("inf")
        batch_size = self.playlist_batch_size

        async def line_generator() -> AsyncIterator[str]:
            """Yield stripped, non-empty lines from the file."""
            if aiofiles:  # async path
                async with aiofiles.open(
                    path, mode="r", encoding="utf-8", errors="replace"
                ) as f:
                    async for raw in f:
                        line = raw.strip()
                        if line:
                            yield line
            else:  # sync fallback (still fast)
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
            count += 1

            if count >= max_items:
                break

            if len(batch) >= batch_size:
                await local_list.mount(*batch)
                batch.clear()
                if count % 500 == 0:
                    await asyncio.sleep(0)

        # Mount any leftovers
        await local_list.mount(*batch)

        if self.fetch_duration_eager:
            asyncio.create_task(self._populate_missing_durations(local_list))

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

    @profile_async
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "play":
            self.mpv.unpause()
            self.update_now_playing(self.current_title, self.option_mode, "▶")
        elif button_id == "pause":
            self.mpv.pause()
            self.update_now_playing(self.current_title, self.option_mode, "⏸")
        elif button_id == "stop":
            self.mpv.stop()
            self.update_now_playing("Nothing playing", "", "⏹")

    @profile_async
    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_id = event.list_view.id
        item = event.item
        if list_id == "station-list" and self.option_mode == "radio":
            station = getattr(item, "data", None)
            if station:
                idx = self.stations.stations.index(station)
                await self.play_station(station, idx)
        elif list_id == "local-list" and self.option_mode == "local":
            file_path = getattr(item, "data", None)
            if file_path:
                if isinstance(file_path, dict):
                    self.play_local(file_path)
                else:
                    self.play_local(file_path)

    def _toast(self, msg: str, extra: str = "", icon: str = ICON_ERR) -> None:
        """Convenient wrapper around `update_now_playing`."""
        self.update_now_playing(msg, extra, icon)

    async def _maybe_run_in_thread(self, func, *args, **kwargs):
        """Run a synchronous function in a thread and return its result."""
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        return await asyncio.to_thread(func, *args, **kwargs)

    @profile_async
    async def on_directory_tree_file_selected(
        self,
        event: DirectoryTree.FileSelected,
    ) -> None:
        """React to a file click in the DirectoryTree."""
        path = Path(event.path)
        ext = path.suffix.lower()

        try:
            # RADIO MODE – JSON stations file
            if self.option_mode == "radio" and ext == ".json":
                success = await self._maybe_run_in_thread(
                    self.stations.update_stations, path
                )
                if success:
                    await self.load_stations_ui()
                    self.notify(f"✅ Loaded stations from {path.name} stations")
                else:
                    self.notify("❌  Failed to load stations ", severity="error")
                return

            # LOCAL MODE – MP3 file (play immediately)
            if self.option_mode == "local" and ext == ".mp3":
                await self._maybe_run_in_thread(self.play_local, path)
                self.notify(f"✅Playing {path.name}")
                return

            # LOCAL MODE – M3U playlist
            if self.option_mode == "local" and ext == ".m3u":
                await self.load_m3u(path)
                self.notify(f"✅Loaded playlist {path.name}")
                return

            # FALLBACK – file type we don't understand
            self.notify(f"❌ Ignored {path.name} (unsupported type)", severity="error")

        except Exception as exc:
            logger.exception("on_directory_tree_file_selected failed")
            self.notify(f"❌ Error: {type(exc).__name__}", severity="error")

    @profile_async
    async def load_stations(self, path: Path) -> None:
        """Load the stations JSON file, build a StationPlayer and populate the ListView."""
        try:
            stations_data = await self._load_json(path)
        except FileNotFoundError:
            logger.warning("Stations file not found: %s", path)
            self.notify(f"⚠️  Stations file not found: {path}", severity="error")
            return
        except json.JSONDecodeError as exc:
            logger.error("Invalid JSON in stations file: %s", exc)
            self.notify(f"❌  Invalid JSON in stations file: {exc}", severity="error")
            return

        self.stations = StationPlayer(self.mpv, stations=stations_data)

        station_list = self.query_one("#station-list", ListView)
        station_list.clear()

        for idx, station in enumerate(self.stations.stations):
            item = ListItem(Label(f"{idx}: {station['name']}"))
            item.data = station  # store the raw dict for later use
            await station_list.mount(item)

        self.notify(f"✅ Loaded {len(self.stations.stations)} stations")

    @profile_async
    async def load_stations_ui(self) -> None:
        """Populate the station ListView from the current ``self.stations`` object."""
        if not self.stations:
            return
        station_list = self.query_one("#station-list", ListView)
        station_list.clear()
        for idx, station in enumerate(self.stations.stations):
            item = ListItem(Label(f"{idx}: {station['name']}"))
            item.data = station
            await station_list.mount(item)

    @profile
    def update_now_playing(self, title: str, source: str, state: str):
        """Update the NowPlaying widget via a single message-posting path.

        The widget is updated exclusively through ``NowPlayingMessage`` —
        there is no direct-assignment fallback, keeping the control flow
        simple and debuggable.
        """
        if title:
            self.current_title = title
        if os.getenv("PYTUIP_DEBUG"):
            try:
                print("[PYTUIP DEBUG] update_now_playing called:", title, source, state)
                traceback.print_stack(limit=3)
            except Exception:
                pass
        try:
            now = self.query_one(NowPlaying)
            msg_title = title if title else self.current_title
            now.post_message(NowPlayingMessage(self, msg_title, source, state))
        except Exception:
            # If the widget isn't mounted (e.g. during tests or early startup),
            # log and ignore — the internal `current_title` preserves state
            logger.debug("NowPlaying widget not mounted; state preserved internally")

    @profile
    def _refresh_metadata(self):
        """Poll for stream/file metadata and update the Now Playing title.

        A *stream* (live radio, or an M3U entry that is a URL) is polled for mpv's
        ``icy-title`` / ``media-title``. A *local file* has its tags read via mutagen
        (falling back to mpv's media-title). Whether to poll as a stream is decided by
        ``self._stream_source`` — not ``option_mode`` — so M3U playlists containing
        radio station URLs are treated as streams and get live metadata.
        """
        if getattr(self, "_stream_source", False):
            self._refresh_stream_metadata()
            return
        if getattr(self, "currently_playing", None) == "local":
            self._refresh_local_metadata()
            return

    @profile
    def _refresh_stream_metadata(self):
        """Poll a live stream for its ``icy-title`` / ``media-title`` and update the title."""
        try:
            if not getattr(self, "_stream_source", False):
                return
            player = getattr(self.mpv, "player", None)
            if player is None:
                return
            # try property API
            meta = None
            if hasattr(player, "get_property"):
                try:
                    meta = player.get_property("icy-title") or player.get_property(
                        "media-title"
                    )
                except Exception:
                    meta = None
            # try attribute fallback
            if not meta:
                meta = getattr(player, "media_title", None) or getattr(
                    player, "title", None
                )
            if meta and meta != self.current_title:
                self.current_title = meta
                self.update_now_playing(meta, "Radio", "▶")
        except Exception:
            logger.debug("_refresh_stream_metadata failed", exc_info=True)

    @profile
    def _refresh_local_metadata(self):
        """Read tags for the currently playing local file and update the title.

        Only does work when a new local source starts playing (the resolved title is
        cached per source), so the 1s poll stays cheap.
        """
        if getattr(self, "currently_playing", None) != "local":
            return
        if getattr(self, "_stream_source", False):
            return
        source = getattr(self, "_current_local_source", None)
        if not source:
            return
        if getattr(self, "_local_meta_source", None) == str(source):
            return
        self._local_meta_source = str(source)

        title = self._read_local_tags(source)
        if not title:
            player = getattr(self.mpv, "player", None)
            if player is not None and hasattr(player, "get_property"):
                try:
                    title = player.get_property("media-title")
                except Exception:
                    logger.debug("media-title read failed", exc_info=True)
        if title and title != self.current_title:
            self.current_title = title
            self.update_now_playing(title, "Local File", "▶")

    @profile
    def _read_local_tags(self, source) -> str | None:
        """Return ``artist - title`` (or the best available) from a file's tags."""
        try:
            info = MutagenFile(str(source), easy=True)
        except Exception:
            logger.debug("mutagen tag read failed for %s", source, exc_info=True)
            return None
        if not info:
            return None
        try:
            artist = (info.get("artist") or [None])[0]
            track = (info.get("title") or [None])[0]
        except Exception:
            logger.debug("unexpected mutagen tag shape for %s", source, exc_info=True)
            return None
        if artist and track:
            return f"{artist} - {track}"
        return track or None

    @profile_async
    async def _load_json(self, path: Path) -> Any:
        async with await open_file(path, mode="r", encoding="utf-8") as f:
            text = await f.read()
            return json.loads(text)

    @profile
    def update_progress(self):
        try:
            pos = self.mpv.get_time_pos()
            dur = self.mpv.get_duration()
        except Exception:
            logger.debug("get_time_pos/get_duration failed", exc_info=True)
            return

        try:
            bar = self.query_one(ProgressBar)
            bar.progress = pos or 0
            bar.duration = dur or 0
        except Exception:
            logger.debug("ProgressBar not available", exc_info=True)
            return
        try:
            if (
                getattr(self, "_stream_source", False)
                and getattr(self, "currently_playing", None) is not None
            ):
                bar.meta = self.current_title or ""
            else:
                bar.meta = ""
        except Exception:
            logger.debug("progress meta update failed", exc_info=True)

        try:
            now = self.query_one(NowPlaying)
            now.progress = pos or 0
            now.duration = dur or 0
            try:
                now.title = self.current_title or now.title
                now.refresh()
            except Exception:
                logger.debug("now playing refresh failed", exc_info=True)
        except Exception:
            logger.debug("now playing update failed", exc_info=True)

    @profile
    def action_toggle_play(self):
        if self.mpv.is_paused():
            self.mpv.unpause()
            self.update_now_playing(self.current_title, self.option_mode, "▶")
        else:
            self.mpv.pause()
            self.update_now_playing(self.current_title, self.option_mode, "⏸")

    @profile
    def action_play(self):
        """Explicit play command (bound to 'p')."""
        try:
            self.mpv.unpause()
        except Exception:
            logger.warning("unpause failed", exc_info=True)
        self.update_now_playing(self.current_title, self.option_mode, "▶")

    @profile
    def action_pause(self):
        """Explicit pause command (bound to 'k')."""
        try:
            self.mpv.pause()
        except Exception:
            logger.warning("pause failed", exc_info=True)
        self.update_now_playing(self.current_title, self.option_mode, "⏸")

    @profile
    def action_stop(self):
        self.mpv.stop()
        self.currently_playing = None
        self._stream_source = False
        self.current_title = "Nothing playing"

        try:
            bar = self.query_one(ProgressBar)
            bar.progress = 0
            bar.duration = 0
        except Exception:
            logger.debug("ProgressBar not available in action_stop", exc_info=True)

        self.update_now_playing("Nothing playing", "", "⏹")

    @profile
    def action_seek_forward(self):
        self.mpv.seek(5)

    @profile
    def action_seek_backward(self):
        self.mpv.seek(-5)

    def _seek_to_percent(self, percent: float):
        """Seek to a percentage of the current duration (0.0-1.0)."""
        try:
            dur = self.mpv.get_duration()
            if not dur or dur <= 0:
                return
            target = int(dur * percent)
            if hasattr(self.mpv, "seek_absolute"):
                self.mpv.seek_absolute(target)
            else:
                pos = self.mpv.get_time_pos() or 0
                self.mpv.seek(target - int(pos))
        except Exception:
            logger.debug("_seek_to_percent failed", exc_info=True)

    def action_seek_to_10(self):
        self._seek_to_percent(0.10)

    def action_seek_to_50(self):
        self._seek_to_percent(0.50)

    def action_seek_to_90(self):
        self._seek_to_percent(0.90)

    @profile_async
    async def play_station(self, station, idx):
        logger.debug("Playing station %d: %s", idx, station.get("name", "unknown"))
        self.stations.play(idx)
        self.currently_playing = "radio"
        self._stream_source = True
        self.current_title = station["name"]
        self.update_now_playing(station["name"], "Radio", "▶")

        try:
            list_view = self.query_one("#station-list", ListView)
            list_view.index = idx
        except Exception:
            logger.debug("station-list not available for index update", exc_info=True)

    @profile
    def play_local(self, path):
        """Play a local file or URL.

        Accepts either:
        - a dict: {"source": <str>, "meta": <label>} (as produced by load_m3u),
        - a Path or string path/URL.
        """
        source = None
        meta_label = None
        if isinstance(path, dict):
            source = path.get("source")
            meta_label = path.get("meta") or path.get("title")
        else:
            source = path

        source_str = None
        source_path = None
        if isinstance(source, Path):
            source_path = source
            source_str = str(source_path)
        else:
            source_str = str(source)

        # If it looks like a URL, hand straight to mpv
        if source_str.startswith(("http://", "https://", "rtmp://", "ftp://")):
            try:
                self.mpv.play(source_str)
            except Exception:
                logger.warning("mpv.play failed for URL %s", source_str, exc_info=True)
            self.currently_playing = "local"
            self._stream_source = True
            self._current_local_source = source_str
            title = meta_label or Path(source_str).name
            self.current_title = title
            try:
                self.update_now_playing(title, "Radio", "▶")
            except Exception:
                logger.debug("update_now_playing failed", exc_info=True)
            return

        # treat as local filesystem path
        try:
            source_path = Path(source_str)
            try:
                source_path = source_path.resolve()
            except Exception:
                logger.debug("path resolution failed", exc_info=True)
            self.mpv.play(str(source_path))
        except Exception:
            try:
                self.mpv.play(source_str)
            except Exception:
                logger.warning("mpv.play failed for %s", source_str, exc_info=True)
                try:
                    self.update_now_playing("Failed to play file", "", "⚠")
                except Exception:
                    logger.debug("update_now_playing failed", exc_info=True)
                return

        self.currently_playing = "local"
        self._stream_source = False
        self._current_local_source = str(source_path or source_str)

        # Determine title: prefer playlist metadata, then tags via mutagen, then filename stem
        title = None
        if meta_label:
            title = meta_label
        else:
            try:
                info = MutagenFile(str(source_path), easy=True)
                album = None
                track = None
                if info:
                    album = info.get("album", [None])[0]
                    track = info.get("title", [None])[0]
                if album and track:
                    title = f"{album} - {track}"
                elif track:
                    title = track
            except Exception:
                logger.debug("mutagen tag read failed", exc_info=True)
                title = None

        if not title:
            try:
                title = Path(source_str).stem
            except Exception:
                title = source_str

        self.current_title = title
        try:
            self.update_now_playing(title, "Local File", "▶")
        except Exception:
            logger.debug("update_now_playing failed", exc_info=True)

    @profile
    def _resolve_playlist_items(self, local_list) -> list:
        """Resolve a list widget's items robustly.

        Textual's ``ListView`` has no ``items`` attribute (only ``children``), while
        test fakes often expose ``items``. Try ``items`` first, then ``children``,
        and never raise — always return a plain list (possibly empty).
        """
        for attr in ("items", "children"):
            try:
                candidate = getattr(local_list, attr, None)
            except Exception:
                logger.debug("reading %s from list widget failed", attr, exc_info=True)
                continue
            if not candidate:
                continue
            try:
                return list(candidate)
            except TypeError:
                logger.debug("list widget %s is not iterable", attr, exc_info=True)
        return []

    @profile
    def action_play_playlist(self) -> None:
        """Start playback from the first item in the local playlist, if any."""
        try:
            local_list = self.query_one("#local-list")
        except Exception:
            logger.warning("No local list widget found")
            self.update_now_playing("No local list", "", "⚠")
            return

        items = self._resolve_playlist_items(local_list)
        if not items:
            logger.debug("No items in playlist")
            self.update_now_playing("No items in playlist", "", "⚠")
            return

        first = items[0]
        data = getattr(first, "data", None)
        if data is None:
            logger.debug("Invalid playlist item (no data)")
            self.update_now_playing("Invalid playlist item", "", "⚠")
            return

        try:
            self.play_local(data)
        except Exception:
            logger.warning("play_local failed for playlist item", exc_info=True)
            self.update_now_playing("Failed to play playlist item", "", "⚠")
            return
        try:
            local_list.index = 0
        except Exception:
            logger.debug("setting list index failed", exc_info=True)
