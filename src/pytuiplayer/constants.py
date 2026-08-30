"""Shared constants for pytuiplayer.

Centralises magic numbers and icon strings so they have a single source of truth
and can be imported by both the app and its tests.
"""

# Maximum number of playlist items to load by default (safety for very large M3U files)
MAX_PLAYLIST_ITEMS = 2000

# Default batch size for mounting playlist items (keeps UI responsive)
DEFAULT_PLAYLIST_BATCH_SIZE = 200

# Icon glyphs used by the toast / status helpers
ICON_OK = "⏺"
ICON_ERR = "⚠"
