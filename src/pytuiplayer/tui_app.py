from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, ListView, ListItem, DirectoryTree, RadioSet, RadioButton
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from pathlib import Path
import os
from pytuiplayer.mpv_player import MPVPlayer
from pytuiplayer.station_player import StationPlayer
import json
from textual.widgets import Static
from textual.message import Message
from textual.reactive import reactive

class NowPlaying(Static):
    title = reactive("Nothing playing")
    state = reactive("⏹")
    source = reactive("")
    progress = reactive(0.0)
    duration = reactive(0.0)
    _offset = reactive(0)

    def on_mount(self) -> None:
        # tick every 0.6s to drive the marquee
        self.set_interval(0.6, self._tick)

    def _tick(self) -> None:
        self._offset = (self._offset + 1) % max(1, len(self.title) + 1)
        self.refresh()

    def on_now_playing_message(self, message: "NowPlayingMessage") -> None:
        # Update widget state when a NowPlayingMessage is posted
        try:
            # Only update title if message provides a non-empty value
            if message.title:
                self.title = message.title
            # Update source if provided
            if message.source:
                self.source = message.source
            # Update state if provided
            if message.state:
                self.state = message.state
            self.refresh()
        except Exception as e:
            # Log error for debugging instead of silently failing
            if os.getenv("PYTUIP_DEBUG"):
                import traceback
                print(f"[PYTUIP ERROR] on_now_playing_message failed: {e}")
                traceback.print_exc()
    def _fmt_mmss(self, seconds: float | None) -> str:
        if not seconds or seconds <= 0:
            return "--:--"
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def _marquee(self, width: int | None = None) -> str:
        text = self.title or ""
        if not text or text == "Nothing playing" or width is None:
            return text
        
        if len(text) <= width:
            return text
                
        buf = text + "   " + text
        start = self._offset
        slice_end = start + width
        if slice_end > len(buf):
            slice_end = len(buf)
        return buf[start:slice_end]

    def render(self) -> str:
        # countdown (remaining) to show at top-left
        remaining = None
        try:
            if self.duration and self.duration > 0:
                remaining = int(self.duration - (self.progress or 0))
        except Exception:
            remaining = None

        countdown = self._fmt_mmss(remaining) if remaining is not None else "--:--"

        title_text = self.title or "Nothing playing"

        # Determine whether to use a scrolling marquee based on available width.
        try:
            size = getattr(self, "size", None)
            if size and getattr(size, "width", 0):
                total_width = size.width
                # Reserved characters for countdown, labels, source and state
                reserved = len(f"[{countdown}] Now Playing: ")
                if self.source:
                    reserved += len(f" | {self.source}")
                reserved += len(self.state or "") + 2
                avail = max(0, total_width - reserved)
                if avail > 10 and len(title_text) > avail:
                    marquee = self._marquee(avail)
                else:
                    marquee = title_text
            else:
                # In contexts where widget size isn't available (tests), prefer
                # non-scrolling full text so assertions are deterministic.
                marquee = self._marquee() or title_text
        except Exception:
            marquee = self._marquee() or title_text

        # Build compact display: [countdown] Title | Source | State
        parts = [f"[{countdown}]", "Now Playing:"]

        if title_text and title_text != "Nothing playing":
            parts.append(marquee)
        else:
            parts.append("Nothing playing")

        if self.source:
            parts.append(f"| {self.source}")

        parts.append(self.state)

        return " ".join(parts)


class NowPlayingMessage(Message):
    """Message used to inform the NowPlaying widget of a title/source/state update."""
    def __init__(self, sender, title: str, source: str, state: str):
        super().__init__()
        self.sender = sender
        self.title = title
        self.source = source
        self.state = state

class ProgressBar(Static):
    progress = reactive(0.0)
    duration = reactive(0.0)
    meta = reactive("")

    def _fmt_mmss(self, seconds: float | None) -> str:
        if not seconds or seconds <= 0:
            return "--:--"
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def render(self) -> str:
        # Unknown duration -> if we have radio metadata, show it on the progress area
        if not self.duration or self.duration <= 0:
            if self.meta:
                # compact display for metadata
                return f"Now: {self.meta}"
            return "⏱ --:-- / --:--"

        # Compute progress bar proportionally and clamp between 0 and 1
        try:
            ratio = max(0.0, min(1.0, (self.progress or 0) / self.duration))
        except Exception:
            ratio = 0.0

        filled = int(ratio * 160)
        bar = "█" * filled + "░" * (160 - filled)

        elapsed = self._fmt_mmss(self.progress)
        total = self._fmt_mmss(self.duration)

        return f"[{bar}] {elapsed} / {total}"


class VolumeIndicator(Static):
    volume = reactive(50)
    muted = reactive(False)
    def render(self) -> str:
        vol = "🔇" if self.muted else f"🔊{self.volume}"
        return f"Volume: {vol}"


class MusicPlayerApp(App):
    CSS_PATH = "musicplayer_tui.css"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding("space", "toggle_play", "Play/Pause"),
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
    ]

    # Maximum number of playlist items to load by default (safety for very large M3U files)
    MAX_PLAYLIST_ITEMS = 2000

    def __init__(self):
        super().__init__()
        self.mpv = MPVPlayer()
        self.stations = None
        self.currently_playing = None
        self.option_mode = "radio"  # default
        self.stations_file = Path(__file__).parent / "stations.json"
        self.current_title = "Nothing playing"

        # Volume state
        self.volume = 50
        self.muted = False
        self._prev_volume = self.volume

        # Playlist loading controls (can be overridden in tests or by callers)
        self.max_playlist_items = self.MAX_PLAYLIST_ITEMS
        self.playlist_batch_size = 200


    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        # Full-width now playing display at top

        yield NowPlaying(id="now-playing")
        yield ProgressBar(id="progress")
            
        # Playback controls
        with Horizontal(id="controls"):    
            yield Button("▶ Play", id="play")
            yield Button("⏸ Pause", id="pause")
            yield Button("⏹ Stop", id="stop")
            yield VolumeIndicator(id="volume-indicator")
            
        
        # Main content: mode selector and lists
        with Horizontal(id="main-content"):
            # Left sidebar: options
            with Vertical(id="sidebar"):
                yield RadioSet(
                    RadioButton("Radio", id="radio-option", value=True),
                    RadioButton("Local", id="local-option", value=False),
                    id="option-set"
                )
            
            # Right content: lists
            with Vertical(id="content"):
                yield ListView(id="station-list")
                yield DirectoryTree(str(Path.home()), id="directory-tree")
                with ListView(id="local-list") as local_list:
                    local_list.border_title = "Local Music List"



    async def on_mount(self) -> None:
        self.title = "Music Player"
        await self.load_stations(self.stations_file)
        # initialize player volume (we keep internal volume handling but hide UI controls)
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            pass
        self.update_volume_ui()
        # progress update and metadata polling
        self.set_interval(0.5, self.update_progress)
        self.set_interval(1.0, self._refresh_metadata)

        # Ensure only the active list is visible at startup. Use both `display`
        # (sends Hide/Show events) and `visible` for compatibility.
        try:
            station = self.query_one("#station-list")
            local = self.query_one("#local-list")
            tree = self.query_one("#directory-tree")
            if self.option_mode == "radio":
                try: station.display = True
                except Exception: pass
                station.visible = True
                station.disabled = False

                for w in (local, tree):
                    try: w.display = False
                    except Exception: pass
                    w.visible = False
                    w.disabled = True
            else:
                try: local.display = True
                except Exception: pass
                local.visible = True
                local.disabled = False
                try: tree.display = True
                except Exception: pass
                tree.visible = True
                tree.disabled = False

                try: station.display = False
                except Exception: pass
                station.visible = False
                station.disabled = True
        except Exception:
            pass
        # Initialize Now Playing display from internal state
        try:
            self.update_now_playing(self.current_title, "", "⏹")
        except Exception:
            pass

    def update_volume_ui(self):
        try:
            vol = self.query_one("#volume-indicator", VolumeIndicator)
            vol.volume = self.volume
            vol.muted = self.muted
        except Exception:
            return

    def action_volume_up(self):
        self.volume = min(100, getattr(self, "volume", 50) + 5)
        if self.muted:
            self.muted = False
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            pass
        self.update_volume_ui()

    def action_volume_down(self):
        self.volume = max(0, getattr(self, "volume", 50) - 5)
        if self.volume == 0:
            self.muted = True
        else:
            self.muted = False
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            pass
        self.update_volume_ui()

    def action_toggle_mute(self):
        if not getattr(self, "muted", False):
            self._prev_volume = getattr(self, "volume", 50)
            self.muted = True
            try:
                self.mpv.set_volume(0)
            except Exception:
                pass
        else:
            self.muted = False
            self.volume = getattr(self, "_prev_volume", 50)
            try:
                self.mpv.set_volume(self.volume)
            except Exception:
                pass
        self.update_volume_ui()


    async def load_stations(self, path: Path):
        try:
            with open(path, "r") as f:
                self.stations = StationPlayer(self.mpv, stations=json.load(f))
        except FileNotFoundError:
            default_file = Path(__file__).parent / "stations.json"
            self.stations = StationPlayer(self.mpv, stations=json.load(default_file))
        station_list = self.query_one("#station-list", ListView)
        station_list.clear()
        for idx, station in enumerate(self.stations.stations):
            item = ListItem(Label(f"{idx}: {station['name']}"))
            item.data = station
            await station_list.mount(item)

    async def on_radio_set_changed(self, event):
        radio = event.pressed.id == "radio-option"
        new_mode = "radio" if radio else "local"

        if self.option_mode != new_mode:
            self.mpv.stop()
            self.current_title = "Nothing playing"
            self.update_now_playing("Nothing playing", "", "⏹")

        self.option_mode = new_mode

        # Use display/visible/disabled so Textual will emit Hide/Show events
        try:
            station = self.query_one("#station-list")
            local = self.query_one("#local-list")
            tree = self.query_one("#directory-tree")
            if radio:
                try: station.display = True
                except Exception: pass
                station.visible = True
                station.disabled = False

                for w in (local, tree):
                    try: w.display = False
                    except Exception: pass
                    w.visible = False
                    w.disabled = True
            else:
                for w in (local, tree):
                    try: w.display = True
                    except Exception: pass
                    w.visible = True
                    w.disabled = False

                try: station.display = False
                except Exception: pass
                station.visible = False
                station.disabled = True
        except Exception:
            # fallback to previous behavior if query fails
            self.query_one("#station-list").visible = radio
            self.query_one("#local-list").visible = not radio
            self.query_one("#station-list").disabled = not radio
            self.query_one("#local-list").disabled = radio

        if not radio:
            await self.load_local_files(Path.home())


    async def load_local_files(self, path: Path):
        """Populate `#local-list` with local music files (case-insensitive).

        We iterate `path.iterdir()` to support uppercase or mixed-case extensions
        instead of relying on a single glob pattern.
        """
        local_list = self.query_one("#local-list", ListView)
        local_list.clear()
        for file in path.iterdir():
            # simple case-insensitive suffix check
            try:
                if file.suffix.lower() == ".mp3":
                    item = ListItem(Label(file.name))
                    item.data = file
                    await local_list.mount(item)
            except Exception:
                # ignore files we cannot stat or inspect
                continue

    async def load_m3u(self, path: Path):
        """Load a local M3U playlist into `#local-list` in batches.

        - Supports `#EXTINF` metadata lines and resolves relative paths against
          the playlist file location.
        - Mounts items in batches and yields to the event loop between batches
          to avoid blocking the UI when playlists are large.
        - Respects `self.max_playlist_items` to avoid loading excessively large
          playlists by default.
        """
        local_list = self.query_one("#local-list", ListView)
        local_list.clear()

        base = path.parent
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                # read lines into memory (OK for typical playlists); we need the
                # data available after file context closes
                lines = [l.strip() for l in f if l.strip()]
        except Exception:
            return

        entries = []  # collect tuples of (source, label) where source may be URL or string path
        metadata_next = None
        for line in lines:
            if line.startswith("#EXTINF"):
                parts = line.split(",", 1)
                metadata_next = parts[1].strip() if len(parts) > 1 else None
                continue
            if line.startswith("#"):
                continue
            # Determine whether this is a URL or a local file path. Avoid
            # resolving local paths at load time to prevent unnecessary IO.
            if line.startswith(("http://", "https://", "rtmp://", "ftp://")):
                source = line
            else:
                candidate = Path(line)
                if candidate.is_absolute():
                    source = str(candidate)
                else:
                    # keep a relative/combined path string; resolution is deferred
                    source = str(base / candidate)

            label = metadata_next or Path(source).name
            metadata_next = None
            entries.append((source, label))

            # enforce a hard limit if configured
            if self.max_playlist_items and len(entries) >= self.max_playlist_items:
                break

        # Mount in batches and yield to the event loop between batches
        import asyncio
        batch = []
        count = 0
        for candidate, label in entries:
            item = ListItem(Label(label))
            # store both the original source (string or url) and the parsed
            # metadata label so the play handler can resolve/verify only when
            # the user actually requests playback.
            item.data = {"source": candidate, "meta": label}
            try:
                item._meta_label = label
            except Exception:
                pass
            batch.append(item)
            count += 1
            if len(batch) >= self.playlist_batch_size:
                for it in batch:
                    await local_list.mount(it)
                batch = []
                # yield control so UI remains responsive
                await asyncio.sleep(0)
        # mount any remaining items
        for it in batch:
            await local_list.mount(it)

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
                # support the new dictionary-shaped data added by load_m3u
                # while remaining backwards compatible with a plain Path/str
                if isinstance(file_path, dict):
                    self.play_local(file_path)
                else:
                    self.play_local(file_path)

    async def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if self.option_mode == "radio" and path.suffix.lower() == ".json":
            # Try updating stations from the selected file. If successful, refresh the
            # station list UI; otherwise surface a simple notification in the
            # NowPlaying widget.
            success = self.stations.update_stations(path)
            if success:
                await self.load_stations_ui()
                self.update_now_playing(f"Loaded stations from {path.name}", "", "⏺")
            else:
                self.update_now_playing("Failed to load stations", "", "⚠")
        elif self.option_mode == "local" and path.suffix.lower() == ".mp3":
            # If a user clicks a file in the directory tree while in Local mode,
            # play it immediately (expected behavior) rather than only setting a
            # flag.
            try:
                self.play_local(path)
            except Exception:
                # Surface a basic notification on failure
                self.update_now_playing("Failed to play file", "", "⚠")
        elif self.option_mode == "local" and path.suffix.lower() == ".m3u":
            # Load an M3U playlist into the local list
            try:
                await self.load_m3u(path)
                self.update_now_playing(f"Loaded playlist {path.name}", "", "⏺")
            except Exception:
                self.update_now_playing("Failed to load playlist", "", "⚠")

    async def load_stations_ui(self):
        """Populate the `#station-list` ListView from the current `self.stations` data."""
        station_list = self.query_one("#station-list", ListView)
        station_list.clear()
        for idx, station in enumerate(self.stations.stations):
            item = ListItem(Label(f"{idx}: {station['name']}"))
            item.data = station
            await station_list.mount(item)
            
    def update_now_playing(self, title: str, source: str, state: str):
        # Keep internal state even if the NowPlaying widget is not available.
        # Do not overwrite an existing title with an empty string — preserve
        # the last-known title unless an explicit non-empty title is provided.
        if title:
            self.current_title = title
        # optional debug logging to trace why UI may clear the title
        if os.getenv("PYTUIP_DEBUG"):
            try:
                import traceback
                print("[PYTUIP DEBUG] update_now_playing called:", title, source, state)
                traceback.print_stack(limit=3)
            except Exception:
                pass
        try:
            now = self.query_one(NowPlaying)
            # Post a message to the widget so it can update itself and
            # participate in Textual's message lifecycle.
            # Use self.current_title (preserved state) as fallback when title is empty
            msg_title = title if title else self.current_title
            try:
                now.post_message(NowPlayingMessage(self, msg_title, source, state))
            except Exception as e:
                # widget might not accept messages in some contexts; fall back to direct assignment
                # This ensures the widget gets updated even if post_message fails
                if os.getenv("PYTUIP_DEBUG"):
                    print(f"[PYTUIP ERROR] post_message failed: {e}")
                try:
                    now.title = msg_title
                    now.source = source
                    now.state = state
                    now.refresh()
                except Exception as e2:
                    if os.getenv("PYTUIP_DEBUG"):
                        print(f"[PYTUIP ERROR] direct assignment fallback also failed: {e2}")
        except Exception as e:
            # If the widget isn't mounted (e.g. during tests or early startup),
            # log and ignore — the internal `current_title` preserves state
            if os.getenv("PYTUIP_DEBUG"):
                print(f"[PYTUIP DEBUG] NowPlaying widget not mounted: {e}")
            return

    def _refresh_metadata(self):
        # Poll MPV for stream metadata (icy-title / media-title) when radio is playing
        try:
            if self.option_mode != "radio":
                return
            if getattr(self, "currently_playing", None) != "radio":
                return
            player = getattr(self.mpv, "player", None)
            meta = None
            if player is None:
                return
            # try property API
            if hasattr(player, "get_property"):
                try:
                    meta = player.get_property("icy-title") or player.get_property("media-title")
                except Exception:
                    meta = None
            # try attribute fallback
            if not meta:
                meta = getattr(player, "media_title", None) or getattr(player, "title", None)
            if meta and meta != self.current_title:
                self.current_title = meta
                self.update_now_playing(meta, "Radio", "▶")
        except Exception:
            return

    def update_progress(self):
        try:
            pos = self.mpv.get_time_pos()
            dur = self.mpv.get_duration()
        except Exception:
            return

        bar = self.query_one(ProgressBar)
        bar.progress = pos or 0
        bar.duration = dur or 0
        # show radio metadata on the progress area when duration unknown
        try:
            if getattr(self, "option_mode", "radio") == "radio" and getattr(self, "currently_playing", None) == "radio":
                bar.meta = self.current_title or ""
            else:
                bar.meta = ""
        except Exception:
            pass

        # also update now playing for countdown purposes
        try:
            now = self.query_one(NowPlaying)
            now.progress = pos or 0
            now.duration = dur or 0
            # Ensure the NowPlaying widget continues to show the preserved
            # `current_title` (defensive in case other code paths briefly
            # set the widget title to an empty string).
            try:
                now.title = self.current_title or now.title
                now.refresh()
            except Exception:
                pass
        except Exception:
            pass

    def action_toggle_play(self):
        if self.mpv.is_paused():
            self.mpv.unpause()
            self.update_now_playing(
                self.current_title, self.option_mode, "▶"
            )
        else:
            self.mpv.pause()
            self.update_now_playing(
                self.current_title, self.option_mode, "⏸"
            )

    def action_play(self):
        """Explicit play command (bound to 'p')."""
        try:
            self.mpv.unpause()
        except Exception:
            pass
        self.update_now_playing(self.current_title, self.option_mode, "▶")

    def action_pause(self):
        """Explicit pause command (bound to 'k')."""
        try:
            self.mpv.pause()
        except Exception:
            pass
        self.update_now_playing(self.current_title, self.option_mode, "⏸")

    def action_stop(self):
        self.mpv.stop()
        self.current_title = "Nothing playing"

        bar = self.query_one(ProgressBar)
        bar.progress = 0
        bar.duration = 0

        self.update_now_playing("Nothing playing", "", "⏹")

    def action_seek_forward(self):
        self.mpv.seek(5)

    def action_seek_backward(self):
        self.mpv.seek(-5)

    def _seek_to_percent(self, percent: float):
        """Seek to a percentage of the current duration (0.0-1.0)."""
        try:
            dur = self.mpv.get_duration()
            if not dur or dur <= 0:
                # no-op when duration is unknown
                return
            target = int(dur * percent)
            # prefer absolute seek if available
            if hasattr(self.mpv, "seek_absolute"):
                self.mpv.seek_absolute(target)
            else:
                # fallback: compute relative from current position
                pos = self.mpv.get_time_pos() or 0
                self.mpv.seek(target - int(pos))
        except Exception:
            return

    def action_seek_to_10(self):
        self._seek_to_percent(0.10)

    def action_seek_to_50(self):
        self._seek_to_percent(0.50)

    def action_seek_to_90(self):
        self._seek_to_percent(0.90)

    async def play_station(self, station, idx):
        self.stations.play(idx)
        self.currently_playing = "radio"
        # show station name until stream metadata arrives
        self.current_title = station["name"]
        self.update_now_playing(
            station["name"], "Radio", "▶"
        )

        list_view = self.query_one("#station-list", ListView)
        list_view.index = idx

    def play_local(self, path):
        """Play a local file or URL.

        Accepts either:
        - a dict: {"source": <str>, "meta": <label>} (as produced by load_m3u),
        - a Path or string path/URL.

        Resolution and file existence checks are deferred until playback is
        requested so we don't perform IO while merely listing playlist items.
        """
        source = None
        meta_label = None
        # support dictionary-shaped data from load_m3u
        if isinstance(path, dict):
            source = path.get("source")
            meta_label = path.get("meta")
        else:
            source = path

        # If this is already a Path object, keep it; else coerce to string
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
                pass
            self.currently_playing = "local"
            # prefer playlist-provided metadata when available
            title = meta_label or Path(source_str).name
            self.current_title = title
            try:
                self.update_now_playing(title, "Local File", "▶")
            except Exception:
                pass
            return

        # treat as local filesystem path; attempt to resolve now that user asked to play
        try:
            source_path = Path(source_str)
            try:
                source_path = source_path.resolve()
            except Exception:
                # resolution failed; keep as-is
                pass
            self.mpv.play(str(source_path))
        except Exception:
            try:
                # best-effort: pass string to mpv
                self.mpv.play(source_str)
            except Exception:
                # can't play this source
                try:
                    self.update_now_playing("Failed to play file", "", "⚠")
                except Exception:
                    pass
                return

        self.currently_playing = "local"

        # Determine title: prefer playlist metadata, then tags via mutagen, then filename stem
        title = None
        if meta_label:
            title = meta_label
        else:
            try:
                from mutagen import File as MutagenFile
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
            pass

    def action_play_playlist(self):
        """Start playback from the first item in the local playlist, if any."""
        try:
            local_list = self.query_one("#local-list")
        except Exception:
            # nothing mounted
            self.update_now_playing("No local list", "", "⚠")
            return

        # Try common list storage attributes used in tests and by Textual
        items = getattr(local_list, "items", None) or getattr(local_list, "children", None)
        if not items:
            self.update_now_playing("No items in playlist", "", "⚠")
            return

        first = items[0]
        data = getattr(first, "data", None)
        if data is None:
            self.update_now_playing("Invalid playlist item", "", "⚠")
            return

        # play and set the UI index if available
        try:
            self.play_local(data)
        except Exception:
            self.update_now_playing("Failed to play playlist item", "", "⚠")
            return
        try:
            # if underlying ListView supports `index`, set it to 0
            local_list.index = 0
        except Exception:
            pass


