"""Main Textual app for pytuiplayer.

Thin orchestrator: routes events to focused modules (volume, metadata, playlist, station_player).
"""

import asyncio
import os
import traceback
from pathlib import Path

from anyio import open_file
from mutagen import File as MutagenFile
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
)

from pytuiplayer.constants import (
    DEFAULT_PLAYLIST_BATCH_SIZE,
    ICON_ERR,
    MAX_PLAYLIST_ITEMS,
)
from pytuiplayer.exporter import PlaylistExporter
from pytuiplayer.history import HistoryTracker
from pytuiplayer.logging_config import get_logger, setup_logging
from pytuiplayer.metadata import MetadataPoller
from pytuiplayer.mpv_player import MPVPlayer
from pytuiplayer.playlist import PlaylistLoader, PlaylistNavigator
from pytuiplayer.profiling import profile, profile_async
from pytuiplayer.screens import LocalScreen, RadioScreen
from pytuiplayer.station_player import StationPlayer
from pytuiplayer.volume import VolumeController
from pytuiplayer.widgets import NowPlaying, NowPlayingMessage

logger = get_logger("tui_app")


class MusicPlayerApp(App):
    """Terminal music player with radio and local playback modes."""

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
        Binding("H", "play_history_last", description="Replay last played item"),
        Binding("z", "toggle_shuffle", description="Toggle shuffle"),
        Binding("r", "cycle_repeat", description="Cycle repeat mode"),
        Binding("e", "export_playlist", description="Export playlist to M3U"),
        Binding("/", action="focus_search", description="Focus search input"),
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
        self._stream_source = False
        self.option_mode = "radio"
        self.stations_file = Path(__file__).parent / "stations.json"
        self.current_title = "Nothing playing"

        # Volume state
        self.volume = 50
        self.muted = False
        self._prev_volume = self.volume

        # Playlist loading controls
        self.max_playlist_items = MAX_PLAYLIST_ITEMS
        self.playlist_batch_size = DEFAULT_PLAYLIST_BATCH_SIZE
        self.fetch_duration_eager = False
        self.local_items = {}

        # Shuffle / repeat playback modes (Low Priority #4)
        self.shuffle = False
        self.repeat = "off"  # "off" | "one" | "all"

        # Local-file metadata polling state
        self._current_local_source = None
        self._local_meta_source = None

        # Controllers
        self.volume_controller = VolumeController(self)
        self.metadata_poller = MetadataPoller(self)
        self.playlist_loader = PlaylistLoader(self)
        self.playlist_navigator = PlaylistNavigator(self)
        self.history_tracker = HistoryTracker(self)
        self.playlist_exporter = PlaylistExporter(self)

    MAX_PLAYLIST_ITEMS = MAX_PLAYLIST_ITEMS

    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()

    @profile_async
    async def on_mount(self) -> None:
        setup_logging()
        logger.info("Application mounted")
        self.title = "Music Player"
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            logger.debug("set_volume failed on mount", exc_info=True)
        self.set_interval(0.5, self.update_progress)
        self.set_interval(1.0, self.metadata_poller.refresh)
        self.push_screen(RadioScreen())

    # === Volume actions (delegate to VolumeController) ===

    def action_volume_up(self):
        self.volume_controller.action_volume_up()

    def action_volume_down(self):
        self.volume_controller.action_volume_down()

    def action_toggle_mute(self):
        self.volume_controller.action_toggle_mute()

    # === Playback actions ===

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
        try:
            self.mpv.unpause()
        except Exception:
            logger.warning("unpause failed", exc_info=True)
        self.update_now_playing(self.current_title, self.option_mode, "▶")

    @profile
    def action_pause(self):
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
        self._clear_playing_tags()

        try:
            bar = self.query_one(NowPlaying)
            bar.progress = 0
            bar.duration = 0
        except Exception:
            logger.debug("NowPlaying not available in action_stop", exc_info=True)

        self.update_now_playing("Nothing playing", "", "⏹")

    @profile
    def action_seek_forward(self):
        self.mpv.seek(5)

    @profile
    def action_seek_backward(self):
        self.mpv.seek(-5)

    def _seek_to_percent(self, percent: float):
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

    # === Metadata polling (thin wrapper for backward compatibility) ===

    def _refresh_metadata(self):
        self.metadata_poller.refresh()

    # === Playlist loading (thin wrappers for backward compatibility) ===

    @profile_async
    async def load_local_files(self, path: Path):
        await self.playlist_loader.load_local_files(path)

    @profile_async
    async def load_m3u(self, path: Path):
        await self.playlist_loader.load_m3u(path)

    async def fetch_duration(self, item: ListItem) -> None:
        await self.playlist_loader.fetch_duration(item)

    async def _populate_missing_durations(self, list_view: ListView):
        await self.playlist_loader._populate_missing_durations(list_view)

    # === Playlist navigation (delegate to PlaylistNavigator) ===

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
        elif button_id == "prev":
            await self.playlist_navigator.play_previous()
        elif button_id == "next":
            await self.playlist_navigator.play_next()

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

    def action_focus_search(self) -> None:
        """Focus the search input (bound to /)."""
        try:
            search_input = self.query_one("#search-input", Input)
            search_input.focus()
        except Exception:
            logger.debug("search-input not available")

    def action_play_history_last(self) -> None:
        """Replay the most recently played item (bound to H / shift+h)."""
        entry = self.history_tracker.replay(0)
        if entry is None:
            logger.debug("play_history_last: no history")
            self.update_now_playing("No history yet", "", "⚠")
            return
        try:
            if entry["mode"] == "radio":
                # Find the station index if still present, else play by URL.
                station = {"name": entry["title"], "url": entry["source"]}
                if self.stations and entry["source"] in {
                    s.get("url") for s in self.stations.stations
                }:
                    idx = next(
                        i for i, s in enumerate(self.stations.stations)
                        if s.get("url") == entry["source"]
                    )
                    asyncio.run(self.play_station(station, idx))
                else:
                    # Play the raw URL (station list may have changed).
                    self.mpv.play(entry["source"])
                    self.currently_playing = "radio"
                    self._stream_source = True
                    self.current_title = entry["title"]
                    self.update_now_playing(entry["title"], "Radio", "▶")
            else:
                self.play_local(entry["source"])
        except Exception:
            logger.warning("play_history_last failed", exc_info=True)
            self.update_now_playing("Failed to replay history", "", "⚠")

    def recent_history(self, n: int | None = None) -> list[dict]:
        """Thin accessor so tests / UI can read recent history."""
        return self.history_tracker.recent(n)

    @profile
    def action_toggle_shuffle(self) -> None:
        """Toggle shuffle mode (bound to z)."""
        self.shuffle = not self.shuffle
        try:
            now = self.query_one(NowPlaying)
            now.shuffle = self.shuffle
        except Exception:
            logger.debug("NowPlaying not available for shuffle indicator", exc_info=True)
        try:
            self.update_now_playing(
                f"Shuffle {'ON' if self.shuffle else 'OFF'}", "", "🔀"
            )
        except Exception:
            logger.debug("update_now_playing failed in toggle_shuffle", exc_info=True)

    @profile
    def action_cycle_repeat(self) -> None:
        """Cycle repeat mode off -> one -> all -> off (bound to r)."""
        order = ("off", "one", "all")
        idx = order.index(self.repeat)
        self.repeat = order[(idx + 1) % len(order)]
        try:
            now = self.query_one(NowPlaying)
            now.repeat = self.repeat
        except Exception:
            logger.debug("NowPlaying not available for repeat indicator", exc_info=True)
        try:
            self.update_now_playing(
                f"Repeat: {self.repeat.upper()}", "", "🔁"
            )
        except Exception:
            logger.debug("update_now_playing failed in cycle_repeat", exc_info=True)

    @profile
    def action_export_playlist(self) -> None:
        """Export the current local playlist to an M3U file (bound to e)."""
        items = list(getattr(self, "local_items", {}).values())
        if not items:
            logger.debug("export_playlist: nothing to export")
            try:
                self.update_now_playing("Nothing to export", "", "⚠")
            except Exception:
                pass
            return
        try:
            path = self.playlist_exporter.default_export_path()
            written = self.playlist_exporter.export_m3u(path, items)
            try:
                self.update_now_playing(f"Exported {len(items)} tracks", "", "⏺")
            except Exception:
                pass
            logger.info("Playlist exported to %s", written)
        except Exception:
            logger.warning("export_playlist failed", exc_info=True)
            try:
                self.update_now_playing("Export failed", "", "⚠")
            except Exception:
                pass

    def export_playlist_to(self, path) -> Path:
        """Thin accessor: export to an explicit path (used by tests/UI)."""
        items = list(getattr(self, "local_items", {}).values())
        return self.playlist_exporter.export_m3u(path, items)

    # === Mode switching ===

    @profile_async
    async def on_radio_set_changed(self, event):
        """Handle mode switch via screen abstraction."""
        radio = event.pressed.id == "radio-option"
        new_mode = "radio" if radio else "local"

        if self.option_mode != new_mode:
            self.mpv.stop()
            self.currently_playing = None
            self._stream_source = False
            self.current_title = "Nothing playing"
            self._clear_playing_tags()
            self.update_now_playing("Nothing playing", "", "⏹")

        self.option_mode = new_mode

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

    # === Event handlers ===

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
        self.update_now_playing(msg, extra, icon)

    async def _maybe_run_in_thread(self, func, *args, **kwargs):
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
                # Cancel the pending local-file scan (LocalScreen timer)
                try:
                    local_screen = self.screen
                    if hasattr(local_screen, 'cancel_pending_local_load'):
                        local_screen.cancel_pending_local_load()
                except Exception:
                    pass
                await self.playlist_loader.load_m3u(path)
                self.notify(f"✅Loaded playlist {path.name}")
                return

            # FALLBACK – file type we don't understand
            self.notify(f"❌ Ignored {path.name} (unsupported type)", severity="error")

        except Exception as exc:
            logger.exception("on_directory_tree_file_selected failed")
            self.notify(f"❌ Error: {type(exc).__name__}", severity="error")

    # === Station loading ===

    @profile_async
    async def load_stations(self, path: Path) -> None:
        """Load the stations JSON file, build a StationPlayer and populate the ListView."""
        import json
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
            item.data = station
            await station_list.mount(item)

        self.notify(f"✅ Loaded {len(self.stations.stations)} stations")

    @profile_async
    async def load_stations_ui(self) -> None:
        """Populate the station ListView from the current self.stations object."""
        if not self.stations:
            return
        station_list = self.query_one("#station-list", ListView)
        station_list.clear()
        for idx, station in enumerate(self.stations.stations):
            item = ListItem(Label(f"{idx}: {station['name']}"))
            item.data = station
            await station_list.mount(item)

    async def _load_json(self, path: Path):
        async with await open_file(path, mode="r", encoding="utf-8") as f:
            text = await f.read()
            import json
            return json.loads(text)

    # === UI updates ===

    @profile
    def update_now_playing(self, title: str, source: str, state: str):
        """Update the NowPlaying widget via a single message-posting path."""
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
            logger.debug("NowPlaying widget not mounted; state preserved internally")

    @profile
    def update_progress(self):
        try:
            pos = self.mpv.get_time_pos()
            dur = self.mpv.get_duration()
        except Exception:
            logger.debug("get_time_pos/get_duration failed", exc_info=True)
            return

        try:
            bar = self.query_one(NowPlaying)
            bar.progress = pos or 0
            bar.duration = dur or 0
        except Exception:
            logger.debug("NowPlaying not available", exc_info=True)
            return
        try:
            if (
                getattr(self, "_stream_source", False)
                and getattr(self, "currently_playing", None) is not None
            ):
                bar.stream = True
                bar.meta = self.current_title or ""
            else:
                bar.stream = False
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

    # === Play actions ===

    @profile_async
    async def play_station(self, station, idx):
        logger.debug("Playing station %d: %s", idx, station.get("name", "unknown"))
        self.stations.play(idx)
        self.currently_playing = "radio"
        self._stream_source = True
        self.current_title = station["name"]
        # Start in "connecting" state — will clear when metadata arrives
        try:
            now = self.query_one(NowPlaying)
            now.connecting = True
            now.meta = ""
        except Exception:
            pass
        self.update_now_playing(station["name"], "Radio", "▶")
        # Track recently-played item.
        try:
            self.history_tracker.record("radio", station["name"], station["url"])
        except Exception:
            logger.debug("history_tracker.record failed", exc_info=True)

        try:
            list_view = self.query_one("#station-list", ListView)
            list_view.index = idx
            self._tag_playing_item(list_view, idx)
        except Exception:
            logger.debug("station-list not available for index update", exc_info=True)

    def _tag_playing_item(self, list_view, idx: int | None) -> None:
        """Mark the currently-playing list item with a `playing` class and clear others."""
        try:
            children = list(getattr(list_view, "children", []))
            for i, child in enumerate(children):
                if i == idx:
                    child.add_class("playing")
                    child.remove_class("not-playing")
                else:
                    child.add_class("not-playing")
                    child.remove_class("playing")
        except Exception:
            logger.debug("_tag_playing_item failed", exc_info=True)

    def _clear_playing_tags(self) -> None:
        """Remove playing/not-playing classes from all list items."""
        for selector in ("#station-list", "#local-list"):
            try:
                lv = self.query_one(selector, ListView)
                for child in list(getattr(lv, "children", [])):
                    child.remove_class("playing", "not-playing")
            except Exception:
                pass

    def _tag_playing_item_for_source(self, source_str: str) -> None:
        """Find the list item whose data.source matches source_str and tag it."""
        try:
            local_list = self.query_one("#local-list", ListView)
            children = list(getattr(local_list, "children", []))
            for i, child in enumerate(children):
                data = getattr(child, "data", None)
                if isinstance(data, dict):
                    src = data.get("source")
                else:
                    src = getattr(data, "source", None) if data else None
                if src is not None and str(src) == str(source_str):
                    self._tag_playing_item(local_list, i)
                    return
            # No match found — still clear other tags
            for child in children:
                child.remove_class("playing", "not-playing")
        except Exception:
            logger.debug("_tag_playing_item_for_source failed", exc_info=True)

    @profile
    def play_local(self, path):
        """Play a local file or URL."""
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
            # Start in "connecting" state for URL streams
            try:
                now = self.query_one(NowPlaying)
                now.connecting = True
                now.meta = ""
            except Exception:
                pass

            try:
                self.update_now_playing(title, "Radio", "▶")
            except Exception:
                logger.debug("update_now_playing failed", exc_info=True)
            # Track recently-played item (URL stream).
            try:
                self.history_tracker.record("local", title, source_str)
            except Exception:
                logger.debug("history_tracker.record failed", exc_info=True)

            # Tag the playing item in the local list
            self._tag_playing_item_for_source(source_str)
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
        # Track recently-played item (local file).
        try:
            self.history_tracker.record("local", title, source_path or source_str)
        except Exception:
            logger.debug("history_tracker.record failed", exc_info=True)

        # Tag the playing item in the local list
        self._tag_playing_item_for_source(str(source_path or source_str))

    def _resolve_playlist_items(self, local_list) -> list:
        """Resolve a list widget's items robustly."""
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
