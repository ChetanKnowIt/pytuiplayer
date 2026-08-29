from pathlib import Path

from pytuiplayer.mpv_player import MPVPlayer

mpv = MPVPlayer()

audio = Path(__file__).parent / "pytuiplayer/GTA.mp3"
mpv.play(str(audio))

print("Playing local file...")
input("Press Enter to exit")

