import mpv

class MPVPlayer:
    def __init__(self):
        self.player = mpv.MPV(
            ytdl=False,
            input_default_bindings=True,
            input_vo_keyboard=True,
            log_handler=print,
            loglevel="debug"
        )

    def play(self, source: str):
        """
        Play a local file OR a URL / radio stream
        """
        print(f"[MPV] Playing: {source}")
        self.player.play(source)

    def pause(self):
        self.player.pause = True

    def unpause(self):
        self.player.pause = False

    def stop(self):
        self.player.stop()

    def set_volume(self, volume: int):
        self.player.volume = volume

