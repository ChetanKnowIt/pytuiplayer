import json
from pathlib import Path

class StationPlayer:
    def __init__(self, mpv_player, stations=None):
        self.mpv = mpv_player
        if stations is not None:
            self.stations = stations
        else:
            self.stations = self._load_default()

    def _load_default(self):
        path = Path(__file__).parent / "stations.json"
        return json.loads(path.read_text())

    def update_stations(self, new_file: Path):
        try:
            self.stations = json.loads(new_file.read_text())
        except FileNotFoundError:
            print(f"[ERROR] Stations file {new_file} not found, keeping previous stations.")

    def play(self, index: int):
        url = self.stations[index]["url"]
        print(f"[RADIO] Playing station {index}: {url}")
        self.mpv.play(url)
