from pytuiplayer.mpv_player import MPVPlayer


class FakeMPV:
    def __init__(self, *args, **kwargs):
        self.play_calls = []
        self.pause = False
        self.volume = 50
        self.stopped = False
        self.time_pos = 10
        self.duration = 100

    def play(self, src):
        self.play_calls.append(src)

    def stop(self):
        self.stopped = True

    def command(self, *args):
        if len(args) >= 2 and args[0] == "seek":
            try:
                self.time_pos += int(args[1])
            except Exception:
                pass


def test_mpvplayer_play_pause_stop_and_volume():
    fake = FakeMPV()
    mpv = MPVPlayer(player=fake)

    mpv.play("song.mp3")
    assert fake.play_calls == ["song.mp3"]

    mpv.pause()
    assert fake.pause is True

    mpv.unpause()
    assert fake.pause is False

    mpv.set_volume(30)
    assert fake.volume == 30

    assert mpv.is_paused() is False

    mpv.stop()
    assert fake.stopped is True


def test_mpvplayer_seek_and_time_duration():
    fake = FakeMPV()
    mpv = MPVPlayer(player=fake)

    assert mpv.get_time_pos() == 10
    assert mpv.get_duration() == 100

    mpv.seek(5)
    assert mpv.get_time_pos() == 15
