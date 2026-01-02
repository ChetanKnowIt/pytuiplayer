import asyncio
from pytuiplayer.tui_app import MusicPlayerApp, NowPlaying, ProgressBar
from textual.widgets import ListItem, Label


def test_app_shows_nowplaying_during_play_and_progress():
    app = MusicPlayerApp()

    class FakeMPV:
        def __init__(self):
            self.last = None
            self._pos = 0
            self._dur = 0
        def play(self, source):
            self.last = source
        def get_time_pos(self):
            return self._pos
        def get_duration(self):
            return self._dur

    app.mpv = FakeMPV()

    # Prepare widgets that query_one will return
    now_widget = NowPlaying()
    progress_widget = ProgressBar()

    # Prepare a fake local list with one playlist item
    item = ListItem(Label("song.mp3"))
    item.data = {"source": "/tmp/integration.mp3", "meta": "Integrate - Test"}

    class FakeList:
        def __init__(self, items):
            self.items = items

    fake_list = FakeList([item])

    def query_one(selector, *a, **k):
        # allow selectors by id or by class
        if selector == "#local-list":
            return fake_list
        if selector == NowPlaying:
            return now_widget
        if selector == ProgressBar or selector == "#progress":
            return progress_widget
        raise KeyError(selector)

    app.query_one = query_one

    # Start playback of the playlist
    app.action_play_playlist()

    assert app.mpv.last == "/tmp/integration.mp3"
    # update_now_playing should have set the current_title
    assert app.current_title == "Integrate - Test"

    # simulate progress updates and ensure NowPlaying retains title
    app.mpv._pos = 30
    app.mpv._dur = 120
    app.update_progress()

    assert progress_widget.progress == 30
    assert progress_widget.duration == 120
    assert now_widget.title == "Integrate - Test"
