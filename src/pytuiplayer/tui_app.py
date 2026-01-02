from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, ListView, ListItem, DirectoryTree, RadioSet, RadioButton
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from pathlib import Path
from pytuiplayer.mpv_player import MPVPlayer
from pytuiplayer.station_player import StationPlayer
import json


from textual.widgets import Static
from textual.reactive import reactive

class NowPlaying(Static):
    title = reactive("Nothing playing")
    state = reactive("⏹")
    source = reactive("")

    def render(self) -> str:
        return (
            "[b]Now Playing[/b]\n"
            f"{self.state} {self.title}\n"
            f"[dim]{self.source}[/dim]"
        )

class ProgressBar(Static):
    progress = reactive(0.0)
    duration = reactive(0.0)

    def _fmt_mmss(self, seconds: float | None) -> str:
        if not seconds or seconds <= 0:
            return "--:--"
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    def render(self) -> str:
        # Unknown duration -> show placeholder
        if not self.duration or self.duration <= 0:
            return "⏱ --:-- / --:--"

        # Compute progress bar proportionally and clamp between 0 and 1
        try:
            ratio = max(0.0, min(1.0, (self.progress or 0) / self.duration))
        except Exception:
            ratio = 0.0

        filled = int(ratio * 20)
        bar = "█" * filled + "░" * (20 - filled)

        elapsed = self._fmt_mmss(self.progress)
        total = self._fmt_mmss(self.duration)

        return f"[{bar}] {elapsed} / {total}"


class VolumeIndicator(Static):
    volume = reactive(50)
    muted = reactive(False)

    def render(self) -> str:
        if self.muted:
            return "[b]Vol:[/b] MUTED"
        return f"[b]Vol:[/b] {self.volume}%"


class MusicPlayerApp(App):
    CSS_PATH = "musicplayer_tui.css"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding("space", "toggle_play", "Play/Pause"),
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


    def compose(self) -> ComposeResult:
        yield Header()
        yield Footer()
        with Horizontal():
            with Vertical():
                yield RadioSet(
                    RadioButton("Radio", id="radio-option", value=True),
                    RadioButton("Local", id="local-option", value=False),
                    id="option-set"
                )
                yield ListView(id="station-list")
                yield DirectoryTree(str(Path.home()), id="directory-tree")
            with ListView(id="local-list") as local_list:
                local_list.border_title = "Local Music List"

        with Horizontal():
            yield Button("Play", id="play")
            yield Button("Pause", id="pause")
            yield Button("Stop", id="stop")
            yield VolumeIndicator(id="volume-indicator")
            yield NowPlaying(id="now-playing")
            yield ProgressBar(id="progress")



    async def on_mount(self) -> None:
        self.title = "Music Player"
        await self.load_stations(self.stations_file)
        # initialize player volume
        try:
            self.mpv.set_volume(self.volume)
        except Exception:
            pass
        self.update_volume_ui()
        self.set_interval(0.5, self.update_progress)

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

        self.query_one("#station-list").visible = radio
        self.query_one("#local-list").visible = not radio
        self.query_one("#station-list").disabled = not radio
        self.query_one("#local-list").disabled = radio

        if not radio:
            await self.load_local_files(Path.home())


    async def load_local_files(self, path: Path):
        local_list = self.query_one("#local-list", ListView)
        local_list.clear()
        for file in path.glob("*.mp3"):
            item = ListItem(Label(file.name))
            item.data = file
            await local_list.mount(item)

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
            self.currently_playing = "local"

    async def load_stations_ui(self):
        """Populate the `#station-list` ListView from the current `self.stations` data."""
        station_list = self.query_one("#station-list", ListView)
        station_list.clear()
        for idx, station in enumerate(self.stations.stations):
            item = ListItem(Label(f"{idx}: {station['name']}"))
            item.data = station
            await station_list.mount(item)
            
    def update_now_playing(self, title: str, source: str, state: str):
        now = self.query_one(NowPlaying)
        now.title = title
        now.source = source
        now.state = state

    def update_progress(self):
        try:
            pos = self.mpv.get_time_pos()
            dur = self.mpv.get_duration()
        except Exception:
            return

        bar = self.query_one(ProgressBar)
        bar.progress = pos or 0
        bar.duration = dur or 0

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
        self.current_title = station["name"]
        self.update_now_playing(
            station["name"], "Radio", "▶"
        )

        list_view = self.query_one("#station-list", ListView)
        list_view.index = idx

    def play_local(self, path: Path):
        self.mpv.play(str(path))
        self.current_title = path.name
        self.currently_playing = "local"

        self.update_now_playing(
            path.name,
            "Local File",
            "▶"
        )


