import mpv


class MPVPlayer:
    def __init__(self, player=None, player_factory=None, **factory_kwargs):
        """Create an MPVPlayer.

        - If `player` is provided, use it directly (useful for testing).
        - Else if `player_factory` is provided, call it with `**factory_kwargs` to
          obtain a player instance.
        - Else construct a real `mpv.MPV` using reasonable defaults.
        """
        if player is not None:
            self.player = player
        elif player_factory is not None:
            self.player = player_factory(**factory_kwargs)
        else:
            self.player = mpv.MPV(
                ytdl=False,
                input_default_bindings=True,
                input_vo_keyboard=True,
                log_handler=print,
                loglevel="debug",
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
        
    def is_paused(self):
        try:
            return bool(self.player.pause)
        except Exception:
            return False

    def seek(self, seconds: int):
        """Seek relative seconds forward/backward."""
        try:
            # preferred API if available
            if hasattr(self.player, "seek"):
                self.player.seek(seconds)
                return
            # fallback to command-based interface
            if hasattr(self.player, "command"):
                self.player.command("seek", seconds, "relative")
        except Exception:
            return

    def get_time_pos(self):
        try:
            return getattr(self.player, "time_pos", None)
        except Exception:
            return None

    def get_duration(self):
        try:
            return getattr(self.player, "duration", None)
        except Exception:
            return None

