"""Shared type definitions for pytuiplayer.

Defines the unified ``ItemData`` shape so that ``load_local_files``, ``load_m3u``,
and radio selection all emit the same structure and consumers no longer need
``isinstance`` guards on the dict's shape.
"""

from typing import TypedDict


class ItemData(TypedDict, total=False):
    """Unified shape stored on every ``ListItem.data``.

    All three producers (``load_local_files``, ``load_m3u``, radio selection)
    populate the same keys so consumers can access them uniformly.
    """

    source: str | object  # Path, str path, or URL str
    title: str            # Human-readable label (filename / EXTINF title / station name)
    duration: int | None  # Seconds, or None when unknown
    meta: str             # Playlist-provided metadata label (M3U EXTINF)
