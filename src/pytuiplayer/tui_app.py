from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Button, Label, ListView, ListItem, DirectoryTree, RadioSet, RadioButton
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from pathlib import Path
from pytuiplayer.mpv_player import MPVPlayer
from pytuiplayer.station_player import StationPlayer
import json

class MusicPlayerApp(App):
    CSS_PATH = "musicplayer_tui.css"
    BINDINGS = [
        Binding(key="q", action="quit", description="Quit the app"),
    ]

    def __init__(self):
        super().__init__()
        self.mpv = MPVPlayer()
        self.stations = None
        self.currently_playing = None
        self.option_mode = "radio"  # default
        self.stations_file = Path(__file__).parent / "stations.json"

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

    async def on_mount(self) -> None:
        self.title = "Music Player"
        await self.load_stations(self.stations_file)

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
        if event.pressed.id == "radio-option":
            self.option_mode = "radio"
            self.query_one("#station-list").visible = True
            self.query_one("#directory-tree").visible = True
            self.query_one("#local-list").visible = False
        elif event.pressed.id == "local-option":
            self.option_mode = "local"
            self.query_one("#station-list").visible = False
            self.query_one("#directory-tree").visible = True
            self.query_one("#local-list").visible = True
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
            if self.currently_playing:
                self.mpv.unpause()
            elif self.option_mode == "radio" and self.stations.stations:
                self.stations.play(0)
                self.currently_playing = "station"
        elif button_id == "pause":
            self.mpv.pause()
        elif button_id == "stop":
            self.mpv.stop()
            self.currently_playing = None

    async def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_id = event.list_view.id
        item = event.item
        if list_id == "station-list" and self.option_mode == "radio":
            station = getattr(item, "data", None)
            if station:
                idx = self.stations.stations.index(station)
                self.stations.play(idx)
                self.currently_playing = "station"
        elif list_id == "local-list" and self.option_mode == "local":
            file_path = getattr(item, "data", None)
            if file_path:
                self.mpv.play(str(file_path))
                self.currently_playing = "local"

    async def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        path = Path(event.path)
        if self.option_mode == "radio" and path.suffix.lower() == ".json":
            self.stations.update_stations(path)
            await self.load_stations_ui()
        elif self.option_mode == "local" and path.suffix.lower() == ".mp3":
            self.mpv.play(str(path))
            self.currently_playing = "local"
