from pytuiplayer.tui_app import MusicPlayerApp


class FakeMPVPlayer:
    def __init__(self):
        self.paused = True
        self.calls = []

    def pause(self):
        self.paused = True
        self.calls.append("pause")

    def unpause(self):
        self.paused = False
        self.calls.append("unpause")

    def stop(self):
        self.calls.append("stop")

    def is_paused(self):
        return self.paused


def test_tui_toggle_play_and_stop():
    app = MusicPlayerApp()
    # inject fake player
    app.mpv = FakeMPVPlayer()

    # avoid touching the textual DOM during unit tests
    app.update_now_playing = lambda *a, **k: None

    # when initially paused True, toggle should unpause
    app.action_toggle_play()
    assert app.mpv.calls[-1] == "unpause"

    # toggling again should pause
    app.action_toggle_play()
    assert app.mpv.calls[-1] == "pause"

    # test action_stop resets fields and updates progress bar
    bar = type("B", (), {"progress": None, "duration": None})()
    app.query_one = lambda *a, **k: bar
    app.update_now_playing = lambda *a, **k: None

    app.action_stop()
    assert app.current_title == "Nothing playing"
    assert bar.progress == 0
    assert bar.duration == 0
