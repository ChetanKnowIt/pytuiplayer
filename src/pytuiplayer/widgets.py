"""Widgets for pytuiplayer — Winamp-style retro TUI.

Exports: NowPlaying, NowPlayingMessage, ProgressBar, VolumeIndicator.
"""

import os
import traceback

from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static

from pytuiplayer.utils import fmt_mmss


class NowPlaying(Static):
    """Winamp-style LED track display.

    Renders a compact digital readout: position in playlist, elapsed time,
    kHz sample rate, kbps bitrate, and the scrolling track title.
    """

    title = reactive("Nothing playing")
    state = reactive("⏹")
    source = reactive("")
    progress = reactive(0.0)
    duration = reactive(0.0)
    _offset = reactive(0)
    _position = reactive(1)   # track position in playlist (1-based)
    _total = reactive(0)      # total tracks in playlist
    _khz = reactive("44.1")   # sample rate display
    _kbps = reactive("320")   # bitrate display

    def on_mount(self) -> None:
        # tick every 0.5s to drive the marquee — slightly faster than before
        self.set_interval(0.5, self._tick)

    def _tick(self) -> None:
        self._offset = (self._offset + 1) % max(1, len(self.title) + 1)
        self.refresh()

    def on_now_playing_message(self, message: "NowPlayingMessage") -> None:
        """Single update path: apply message fields to the widget."""
        try:
            if message.title:
                self.title = message.title
                self._offset = 0  # reset marquee on new track
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

        # Smooth scrolling: pad with spaces, advance offset
        buf = text + "    " + text
        start = self._offset % len(text)
        slice_end = start + width
        if slice_end > len(buf):
            slice_end = len(buf)
        result = buf[start:slice_end]
        # Pad if at the very end we get fewer chars
        if len(result) < width:
            result += buf[: width - len(result)]
        return result[:width]

    def render(self) -> str:
        # Build the Winamp-style display
        elapsed = fmt_mmss(int(self.progress) if self.progress else 0)
        total_time = fmt_mmss(int(self.duration) if self.duration else 0)

        title_text = self.title or "Nothing playing"

        # Determine marquee width based on available space
        try:
            size = getattr(self, "size", None)
            if size and getattr(size, "width", 0):
                total_width = size.width
                # Reserve for: position + elapsed + "/" + total + khz + kbps + state + padding
                reserved = len("00/00 00:00/00:00 44.1kHz 320kbps ⏹ ")
                avail = max(15, total_width - reserved)
                if len(title_text) > avail:
                    marquee = self._marquee(avail)
                else:
                    marquee = title_text
            else:
                marquee = title_text
        except Exception:
            marquee = title_text

        # Position display: "01/12 " or "   -- " if unknown
        if self._total > 0:
            pos_str = f"{self._position:02d}/{self._total:02d}"
        else:
            pos_str = "--   "

        # Time display: "elapsed/total" or "--:--/--:--"
        time_str = f"{elapsed}/{total_time}"

        # Bottom status line: khz / kbps
        khz_str = f"{self._khz}kHz"
        kbps_str = f"{self._kbps}kbps"

        # Top line: position + time + state
        top = f"{pos_str}  {time_str}  {khz_str} {kbps_str}  {self.state}"

        # Bottom line: marquee title
        return f"{top}\n{marquee}"


class NowPlayingMessage(Message):
    """Message used to inform the NowPlaying widget of a title/source/state update."""

    def __init__(self, sender, title: str, source: str, state: str):
        super().__init__()
        self.sender = sender
        self.title = title
        self.source = source
        self.state = state


class ProgressBar(Static):
    """Winamp-style seek bar with elapsed/total time and clickable progress indicator.

    Renders: ●━━━━━━━ 01:23 / 04:32  (with green bar for played portion)
    For streams (radio): shows metadata title instead of seek bar
    """

    progress = reactive(0.0)
    duration = reactive(0.0)
    meta = reactive("")
    stream = reactive(False)  # True for live streams (radio) — show metadata, not seek bar

    # Minimum / maximum bar width (in characters) to keep it readable
    MIN_BAR_WIDTH = 20
    MAX_BAR_WIDTH = 160

    def render(self) -> str:
        # For streams (radio): always show metadata, even if duration is available
        if self.stream:
            if self.meta:
                return f"Now: {self.meta}"
            if self.duration and self.duration > 0:
                elapsed = fmt_mmss(self.progress)
                total = fmt_mmss(self.duration)
                return f"♪ Streaming  {elapsed} / {total}"
            return "♪ Streaming"

        # Unknown duration -> if we have radio metadata, show it on the progress area
        if not self.duration or self.duration <= 0:
            if self.meta:
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

        # Reserve space for: elapsed(5) + " / " (3) + total(5) + padding + bracket (2)
        reserved = len(" 00:00 / 00:00")
        bar_width = max(self.MIN_BAR_WIDTH, min(self.MAX_BAR_WIDTH, width - reserved))

        # Winamp-style: use a position marker (●) in the bar
        pos = int(ratio * bar_width)
        if pos == 0:
            bar = "●" + "─" * (bar_width - 1)
        elif pos >= bar_width:
            bar = "─" * (bar_width - 1) + "●"
        else:
            bar = "─" * pos + "●" + "─" * (bar_width - pos - 1)

        elapsed = fmt_mmss(self.progress)
        total = fmt_mmss(self.duration)

        return f"{bar} {elapsed} / {total}"


class VolumeIndicator(Static):
    """Winamp-style volume / mute display with a mini bar."""

    volume = reactive(50)
    muted = reactive(False)

    def render(self) -> str:
        if self.muted:
            return "VOL ░░░░░░░░░░  MUTE"

        bar_width = 10
        filled = int((self.volume / 100) * bar_width)
        bar = "█" * filled + "░" * (bar_width - filled)
        return f"VOL {bar} {self.volume:3d}%"
