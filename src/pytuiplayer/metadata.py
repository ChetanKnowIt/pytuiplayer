"""Metadata polling for pytuiplayer.

Polls mpv for stream metadata (icy-title/media-title) and local file tags (mutagen).
"""

from mutagen import File as MutagenFile

from pytuiplayer.logging_config import get_logger
from pytuiplayer.profiling import profile

logger = get_logger("metadata")


class MetadataPoller:
    """Polls for stream/file metadata and updates the NowPlaying widget."""

    def __init__(self, app):
        self.app = app

    @profile
    def refresh(self):
        """Poll for stream/file metadata and update the title."""
        if getattr(self.app, "_stream_source", False):
            self._refresh_stream_metadata()
            return
        if getattr(self.app, "currently_playing", None) == "local":
            self._refresh_local_metadata()
            return

    @profile
    def _refresh_stream_metadata(self):
        """Poll a live stream for its icy-title / media-title and update the title."""
        try:
            if not getattr(self.app, "_stream_source", False):
                return
            player = getattr(self.app.mpv, "player", None)
            if player is None:
                return
            # try property API
            meta = None
            if hasattr(player, "get_property"):
                try:
                    meta = player.get_property("icy-title") or player.get_property(
                        "media-title"
                    )
                except Exception:
                    meta = None
            # try attribute fallback
            if not meta:
                meta = getattr(player, "media_title", None) or getattr(
                    player, "title", None
                )
            if meta and meta != self.app.current_title:
                self.app.current_title = meta
                self.app.update_now_playing(meta, "Radio", "▶")
        except Exception:
            logger.debug("_refresh_stream_metadata failed", exc_info=True)

    @profile
    def _refresh_local_metadata(self):
        """Read tags for the currently playing local file and update the title."""
        if getattr(self.app, "currently_playing", None) != "local":
            return
        if getattr(self.app, "_stream_source", False):
            return
        source = getattr(self.app, "_current_local_source", None)
        if not source:
            return
        if getattr(self.app, "_local_meta_source", None) == str(source):
            return
        self.app._local_meta_source = str(source)

        title = self._read_local_tags(source)
        if not title:
            player = getattr(self.app.mpv, "player", None)
            if player is not None and hasattr(player, "get_property"):
                try:
                    title = player.get_property("media-title")
                except Exception:
                    logger.debug("media-title read failed", exc_info=True)
        if title and title != self.app.current_title:
            self.app.current_title = title
            self.app.update_now_playing(title, "Local File", "▶")

    @profile
    def _read_local_tags(self, source):
        """Return artist - title (or the best available) from a file's tags."""
        try:
            info = MutagenFile(str(source), easy=True)
        except Exception:
            logger.debug("mutagen tag read failed for %s", source, exc_info=True)
            return None
        if not info:
            return None
        try:
            artist = (info.get("artist") or [None])[0]
            track = (info.get("title") or [None])[0]
        except Exception:
            logger.debug("unexpected mutagen tag shape for %s", source, exc_info=True)
            return None
        if artist and track:
            return f"{artist} - {track}"
        return track or None
