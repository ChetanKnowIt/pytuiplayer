import time

from pytuiplayer.mpv_player import MPVPlayer
from pytuiplayer.station_player import StationPlayer

mpv = MPVPlayer()                      
radio_player = StationPlayer(mpv)

print("Test for radio stream")
radio_player.play(2)

# Keep program alive so stream plays
time.sleep(30)

