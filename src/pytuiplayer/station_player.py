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

    def update_stations(self, new_file: Path) -> bool:
        """Update stations from `new_file`.

        Returns True if stations were successfully updated, False otherwise (keeps
        previous stations on failure).
        """
        try:
            self.stations = json.loads(new_file.read_text())
            return True
        except FileNotFoundError:
            print(f"[ERROR] Stations file {new_file} not found, keeping previous stations.")
            return False
        except json.JSONDecodeError as exc:
            print(f"[ERROR] Failed to parse stations file {new_file}: {exc}. Keeping previous stations.")
            return False

    def play(self, index: int):
        url = self.stations[index]["url"]
        print(f"[RADIO] Playing station {index}: {url}")
        self.mpv.play(url)
