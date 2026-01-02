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
        # emulate a relative seek via command('seek', seconds, 'relative')
        if len(args) >= 2 and args[0] == 'seek':
            try:
                self.time_pos += int(args[1])
            except Exception:
                pass


def test_play_pause_stop_and_volume(monkeypatch):
    monkeypatch.setattr('pytuiplayer.mpv_player.mpv.MPV', FakeMPV)
    mpv = MPVPlayer()

    mpv.play('song.mp3')
    assert mpv.player.play_calls == ['song.mp3']

    mpv.pause()
    assert mpv.player.pause is True

    mpv.unpause()
    assert mpv.player.pause is False

    mpv.set_volume(30)
    assert mpv.player.volume == 30

    assert mpv.is_paused() is False

    mpv.stop()
    assert mpv.player.stopped is True


def test_seek_and_time_duration(monkeypatch):
    monkeypatch.setattr('pytuiplayer.mpv_player.mpv.MPV', FakeMPV)
    mpv = MPVPlayer()

    assert mpv.get_time_pos() == 10
    assert mpv.get_duration() == 100

    mpv.seek(5)
    assert mpv.get_time_pos() == 15
