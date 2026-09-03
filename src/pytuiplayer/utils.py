"""Shared helper utilities for pytuiplayer.

Pure functions only — no Textual or mpv dependencies — so they are trivially
unit-testable and reusable across modules.
"""

from pathlib import Path


def parse_extinf(line: str) -> tuple[int | None, str | None]:
    """
    Parse a line that starts with #EXTINF.
    Returns (duration_seconds|None, title|None)
    """
    try:
        # "#EXTINF:213,Song Title"
        _, rest = line.split(":", 1)
        dur_part, title_part = rest.split(",", 1)
        dur = int(dur_part.strip())
        if dur < 0:
            dur = None
        return dur, title_part.strip()
    except Exception:
        return None, None


def resolve_source(base: Path, raw: str) -> str:
    """Resolve a raw playlist entry to a string that can be used later.

    URLs are returned unchanged, local paths are made absolute (but
    we keep them as strings to avoid creating Path objects later).
    Handles M3U backslash escaping (e.g. "\\ " → " ", "\\[" → "[").
    """
    if raw.startswith(("http://", "https://", "rtmp://", "ftp://")):
        return raw

    # Unescape M3U backslash escapes: \ space, \[, \], \=
    unescaped = raw.replace("\\ ", " ").replace("\\[", "[").replace("\\]", "]").replace("\\=", "=")

    cand = Path(unescaped)
    if cand.is_absolute():
        return str(cand)
    # Relative – join with the playlist folder now, but keep as string.
    return str(base / cand)


def fmt_mmss(seconds: float | None) -> str:
    """Format a seconds value as MM:SS, or '--:--' when unknown."""
    if not seconds or seconds <= 0:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"
