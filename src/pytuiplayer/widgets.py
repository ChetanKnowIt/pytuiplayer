"""Widgets for pytuiplayer.

Exports: NowPlaying, NowPlayingMessage, ProgressBar, VolumeIndicator.
"""

import os
import traceback

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from pytuiplayer.utils import fmt_mmss


class NowPlaying(Static):
    """Displays the current track title, source, and playback state.

    State is updated exclusively via :class:`NowPlayingMessage` posted by
    ``MusicPlayerApp.update_now_playing`` — there is no direct-assignment
    fallback, keeping a single, debuggable update path.
    """

    title = reactive("Nothing playing")
    state = reactive("⏹")
    source = reactive("")
    progress = reactive(0.0)
    duration = reactive(0.0)
    _offset = reactive(0)

    def on_mount(self) -> None:
        # tick every 0.6s to drive the marquee
        self.set_interval(0.6, self._tick)

    def _tick(self) -> None:
        self._offset = (self._offset + 1) % max(1, len(self.title) + 1)
        self.refresh()

    def on_now_playing_message(self, message: "NowPlayingMessage") -> None:
        """Single update path: apply message fields to the widget."""
        try:
            if message.title:
                self.title = message.title
            if message.source:
                self.source = message.source
            if message.state:
                self.state = message.state
            self.refresh()
        except Exception:
            if os.getenv("PYTUIP_DEBUG"):
                print("[PYTUIP ERROR] on_now_playing_message failed")
                traceback.print_exc()

    def _marquee(self, width: int | None = None) -> str:
        text = self.title or ""
        if not text or text == "Nothing playing" or width is None:
            return text

        if len(text) <= width:
            return text

        buf = text + "   " + text
        start = self._offset
        slice_end = start + width
        if slice_end > len(buf):
            slice_end = len(buf)
        return buf[start:slice_end]

    def render(self) -> str:
        # countdown (remaining) to show at top-left
        remaining = None
        try:
            if self.duration and self.duration > 0:
                remaining = int(self.duration - (self.progress or 0))
        except Exception:
            remaining = None

        countdown = fmt_mmss(remaining) if remaining is not None else "--:--"

        title_text = self.title or "Nothing playing"

        # Determine whether to use a scrolling marquee based on available width.
        try:
            size = getattr(self, "size", None)
            if size and getattr(size, "width", 0):
                total_width = size.width
                # Reserved characters for countdown, labels, source and state
                reserved = len(f"[{countdown}] Now Playing: ")
                if self.source:
                    reserved += len(f" | {self.source}")
                reserved += len(self.state or "") + 2
                avail = max(0, total_width - reserved)
                if avail > 10 and len(title_text) > avail:
                    marquee = self._marquee(avail)
                else:
                    marquee = title_text
            else:
                # In contexts where widget size isn't available (tests), prefer
                # non-scrolling full text so assertions are deterministic.
                marquee = self._marquee() or title_text
        except Exception:
            marquee = self._marquee() or title_text

        # Build compact display: [countdown] Title | Source | State
        parts = [f"[{countdown}]", "Now Playing:"]

        if title_text and title_text != "Nothing playing":
            parts.append(marquee)
        else:
            parts.append("Nothing playing")

        if self.source:
            parts.append(f"| {self.source}")

        parts.append(self.state)

        return " ".join(parts)


class NowPlayingMessage(Message):
    """Message used to inform the NowPlaying widget of a title/source/state update."""

    def __init__(self, sender, title: str, source: str, state: str):
        super().__init__()
        self.sender = sender
        self.title = title
        self.source = source
        self.state = state


class ProgressBar(Static):
    """Playback progress bar with elapsed/total time and radio metadata.

    Bar width derives from ``self.size.width`` (minus padding) rather than a
    hardcoded character count, so it adapts to the terminal width.
    """

    progress = reactive(0.0)
    duration = reactive(0.0)
    meta = reactive("")

    # Minimum / maximum bar width (in characters) to keep it readable
    MIN_BAR_WIDTH = 20
    MAX_BAR_WIDTH = 160

    def render(self) -> str:
        # Unknown duration -> if we have radio metadata, show it on the progress area
        if not self.duration or self.duration <= 0:
            if self.meta:
                # compact display for metadata
                return f"Now: {self.meta}"
            return "⏱ Duration unknown"

        # Compute progress bar proportionally and clamp between 0 and 1
        try:
            ratio = max(0.0, min(1.0, (self.progress or 0) / self.duration))
        except (Exception, ZeroDivisionError):
            ratio = 0.0

        # Derive bar width from widget size, clamped to a sane range.
        try:
            size = getattr(self, "size", None)
            width = size.width if size and getattr(size, "width", 0) else self.MAX_BAR_WIDTH
        except Exception:
            width = self.MAX_BAR_WIDTH

        # Reserve space for the brackets + elapsed/total + padding
        reserved = len("[") + len("] ") + len(" --:-- / --:--")
        bar_width = max(self.MIN_BAR_WIDTH, min(self.MAX_BAR_WIDTH, width - reserved))

        filled = int(ratio * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)

        elapsed = fmt_mmss(self.progress)
        total = fmt_mmss(self.duration)

        return f"[{bar}] {elapsed} / {total}"


class VolumeIndicator(Static):
    """Volume / mute display."""

    volume = reactive(50)
    muted = reactive(False)

    def render(self) -> str:
        vol = "🔇" if self.muted else f"🔊{self.volume}"
        return f"Volume: {vol}"
