"""Shared constants for pytuiplayer.

Centralises magic numbers and icon strings so they have a single source of truth
and can be imported by both the app and its tests.
"""

from pathlib import Path

# Maximum number of playlist items to load by default (safety for very large M3U files)
MAX_PLAYLIST_ITEMS = 2000

# Default batch size for mounting playlist items (keeps UI responsive)
DEFAULT_PLAYLIST_BATCH_SIZE = 200

# Maximum number of recently-played items to remember in the history tracker
MAX_HISTORY_ITEMS = 200

# Icon glyphs used by the toast / status helpers
ICON_OK = "⏺"
ICON_ERR = "⚠"

# Metadata cache database path (XDG-compliant)
METADATA_DB_DIR = Path.home() / ".local" / "share" / "pytuiplayer"
METADATA_DB_PATH = METADATA_DB_DIR / "metadata.db"
