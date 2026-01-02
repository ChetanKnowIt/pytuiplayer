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

    def render(self) -> str:
        if self.duration <= 0:
            return "⏱ --:-- / --:--"

        filled = int((self.progress / self.duration) * 20)
        bar = "█" * filled + "░" * (20 - filled)

        return f"[{bar}] {int(self.progress):02}s / {int(self.duration):02}s"


class MusicPlayerApp(App):
    CSS_PATH = "musicplayer_tui.css"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
        Binding("space", "toggle_play", "Play/Pause"),
        Binding("s", "stop", "Stop"),
        Binding("h", "seek_backward", "Seek -5s"),
        Binding("l", "seek_forward", "Seek +5s"),
        ]

    def __init__(self):
        super().__init__()
        self.mpv = MPVPlayer()
        self.stations = None
        self.currently_playing = None
        self.option_mode = "radio"  # default
        self.stations_file = Path(__file__).parent / "stations.json"
        self.current_title = "Nothing playing"


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
            yield NowPlaying(id="now-playing")
            yield ProgressBar(id="progress")



    async def on_mount(self) -> None:
        self.title = "Music Player"
        await self.load_stations(self.stations_file)
        self.set_interval(0.5, self.update_progress)


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
            self.stations.update_stations(path)
            await self.load_stations_ui()
        elif self.option_mode == "local" and path.suffix.lower() == ".mp3":
            self.currently_playing = "local"
            
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


