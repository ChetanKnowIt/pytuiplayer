"""Playback history tracking for pytuiplayer.

Records every item the user plays (radio station or local file) into an
in-memory, most-recent-first list, de-duplicating consecutive repeats and
capping the list at ``MAX_HISTORY_ITEMS``. Pure, text-UI-agnostic logic so it
is trivially unit-testable without a Textual DOM or a live mpv instance.
"""

from collections import deque

from pytuiplayer.constants import MAX_HISTORY_ITEMS
from pytuiplayer.logging_config import get_logger
from pytuiplayer.profiling import profile

logger = get_logger("history")


class HistoryTracker:
    """Tracks recently played items for quick replay.

    Each entry is a dict with keys:
        ``mode``   - ``"radio"`` or ``"local"``
        ``title``  - human-readable label (station name or track title)
        ``source`` - the playable source (station URL or file path str)
    """

    def __init__(self, app, max_items: int = MAX_HISTORY_ITEMS):
        self.app = app
        self.max_items = max_items
        # Most-recent-first deque; index 0 == last played.
        self._entries: deque[dict] = deque(maxlen=max_items)

    @profile
    def record(self, mode: str, title: str, source) -> None:
        """Record a played ``(mode, title, source)`` triple.

        Skips duplicates of the most-recent entry (e.g. re-selecting the same
        station) and caps the list at ``max_items`` via the bounded deque.
        """
        if not title or not source:
            return
        source_str = str(source)
        # De-dupe consecutive repeats: if it's identical to the top entry, ignore.
        if self._entries:
            top = self._entries[0]
            if top["mode"] == mode and top["title"] == title and top["source"] == source_str:
                return
        self._entries.appendleft(
            {"mode": mode, "title": title, "source": source_str}
        )

    @profile
    def recent(self, n: int | None = None) -> list[dict]:
        """Return up to ``n`` most-recent entries (oldest-last order).

        Passing ``n=None`` returns the whole (capped) history.
        """
        items = list(self._entries)
        if n is not None:
            items = items[: max(0, n)]
        return items

    @profile
    def replay(self, index: int) -> dict | None:
        """Return the history entry at ``index`` (0 == most recent).

        Returns ``None`` if the index is out of range. Callers replay the item
        by calling ``play_station`` / ``play_local`` with the returned source.
        """
        if index < 0 or index >= len(self._entries):
            return None
        return self._entries[index]

    @profile
    def clear(self) -> None:
        """Empty the history."""
        self._entries.clear()

    @property
    def count(self) -> int:
        return len(self._entries)
