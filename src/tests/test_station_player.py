from pathlib import Path
from pytuiplayer.station_player import StationPlayer


class FakeMPV:
    def __init__(self):
        self.play_calls = []

    def play(self, url):
        self.play_calls.append(url)


def test_stationplayer_play_uses_mpv():
    mpv = FakeMPV()
    stations = [
        {"name": "One", "url": "http://one"},
        {"name": "Two", "url": "http://two"},
    ]
    sp = StationPlayer(mpv, stations=stations)
    sp.play(1)
    assert mpv.play_calls == ["http://two"]


def test_stationplayer_update_stations_reads_file(tmp_path):
    mpv = FakeMPV()
    sp = StationPlayer(mpv, stations=[{"name": "old", "url": "u"}])

    new_file = tmp_path / "new_stations.json"
    new_file.write_text('[{"name": "new","url": "http://n"}]')

    sp.update_stations(new_file)
    assert sp.stations[0]["name"] == "new"

    # missing file keeps previous stations
    sp.update_stations(tmp_path / "does_not_exist.json")
    assert sp.stations[0]["name"] == "new"
