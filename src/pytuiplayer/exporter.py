"""Playlist export for pytuiplayer.

Writes the currently-loaded local playlist (``app.local_items`` — a dict of
``ItemData`` records) to a standard M3U / EXTINF file. Pure file I/O so it is
fully unit-testable without a Textual DOM or a live mpv instance.
"""

from pathlib import Path

from pytuiplayer.logging_config import get_logger
from pytuiplayer.profiling import profile

logger = get_logger("exporter")

M3U_HEADER = "#EXTM3U"


class PlaylistExporter:
    """Exports the in-memory local playlist to an EXTINF M3U file."""

    def __init__(self, app):
        self.app = app

    @profile
    def build_lines(self, items: list[dict]) -> list[str]:
        """Build the M3U lines (without trailing newline) from item dicts.

        Each item is an ``ItemData``-shaped dict: ``source``, ``title``,
        ``duration`` (seconds or None), ``meta`` (optional). The EXTINF
        duration is emitted as an integer; unknown durations use ``-1``.
        """
        lines = [M3U_HEADER]
        for item in items:
            source = item.get("source")
            if source is None:
                continue
            title = item.get("meta") or item.get("title") or Path(str(source)).name
            duration = item.get("duration")
            # M3U wants integer seconds; -1 when unknown.
            ext_dur = int(duration) if isinstance(duration, (int, float)) else -1
            lines.append(f"#EXTINF:{ext_dur},{title}")
            lines.append(str(source))
        return lines

    @profile
    def export_m3u(self, path, items: list[dict] | None = None) -> Path:
        """Write ``items`` (defaults to ``app.local_items`` values) to ``path``.

        Returns the written path. ``path`` may be a str or Path.
        """
        target = Path(path)
        if items is None:
            items = list(getattr(self.app, "local_items", {}).values())
        lines = self.build_lines(items)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        logger.info("Exported %d items to %s", len(items), target)
        return target

    @profile
    def default_export_path(self, name: str = "playlist.m3u") -> Path:
        """Default export location: a playlist file under the music home dir.

        Falls back to the current working directory if ``$HOME`` is unset.
        """
        import os

        base = Path(os.environ.get("HOME", ".")) / "Music" / "pytuiplayer"
        base.mkdir(parents=True, exist_ok=True)
        return base / name
