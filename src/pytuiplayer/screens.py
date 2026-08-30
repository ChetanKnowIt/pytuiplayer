"""Screens for radio and local playback modes.

The app switches between ``RadioScreen`` and ``LocalScreen`` via
``switch_screen`` instead of manually toggling widget visibility, giving a
clean mode-switch abstraction. Each screen composes the shared widgets
(Header, Footer, NowPlaying, ProgressBar, controls) plus its mode-specific
content.
"""

from pathlib import Path

from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    ListView,
    RadioButton,
    RadioSet,
)

from pytuiplayer.widgets import NowPlaying, ProgressBar, VolumeIndicator


class ModeScreen(Screen):
    """Base class for mode screens — composes shared + mode-specific widgets."""

    def compose(self):
        yield Header()
        yield Footer()
        yield NowPlaying(id="now-playing")
        yield ProgressBar(id="progress")
        with Horizontal(id="controls"):
            yield Button("▶ Play", id="play")
            yield Button("⏸ Pause", id="pause")
            yield Button("⏹ Stop", id="stop")
            yield VolumeIndicator(id="volume-indicator")

        with Horizontal(id="main-content"):
            with Vertical(id="sidebar") as sidebar:
                yield RadioSet(
                    RadioButton("Radio", id="radio-option", value=self._radio_value),
                    RadioButton("Local", id="local-option", value=not self._radio_value),
                    id="option-set",
                )
                sidebar.border_title = "Mode Selection"

            with Vertical(id="content"):
                yield from self.compose_mode_content()

    @property
    def _radio_value(self) -> bool:
        """Whether the 'Radio' button should be selected (overridden by subclasses)."""
        return True

    def compose_mode_content(self):
        """Override to yield mode-specific content into the #content area."""
        return
        yield  # unreachable — makes this a generator so Textual can chain it

    def on_mount(self) -> None:
        """Sync shared widget state from the app."""
        try:
            npw = self.query_one("#now-playing", NowPlaying)
            npw.title = self.app.current_title
            npw.state = "⏹"
            npw.source = ""
        except Exception:
            pass
        try:
            vi = self.query_one("#volume-indicator", VolumeIndicator)
            vi.volume = self.app.volume
            vi.muted = self.app.muted
        except Exception:
            pass
        try:
            pb = self.query_one("#progress", ProgressBar)
            pb.progress = 0
            pb.duration = 0
            pb.meta = ""
        except Exception:
            pass


class RadioScreen(ModeScreen):
    """Radio mode: station list with mode selector."""

    @property
    def _radio_value(self) -> bool:
        return True

    def compose_mode_content(self):
        yield ListView(id="station-list")

    def on_mount(self) -> None:
        super().on_mount()
        station_list = self.query_one("#station-list", ListView)
        station_list.border_title = "Radio Stations"
        # Load stations if not already loaded, or re-populate if the list is empty
        # (e.g., after switching back from LocalScreen which creates a fresh RadioScreen).
        if not self.app.stations or not station_list.children:
            self.set_timer(0.1, self._load_stations)

    async def _load_stations(self) -> None:
        try:
            await self.app.load_stations(self.app.stations_file)
        except Exception:
            pass


class LocalScreen(ModeScreen):
    """Local mode: directory tree + local file list with mode selector."""

    @property
    def _radio_value(self) -> bool:
        return False

    def compose_mode_content(self):
        yield DirectoryTree(str(Path.home()), id="directory-tree")
        yield ListView(id="local-list")

    def on_mount(self) -> None:
        super().on_mount()
        local_list = self.query_one("#local-list", ListView)
        local_list.border_title = "Local Music List"
        # Load local files after the screen is fully mounted so widgets are available.
        self.set_timer(0.1, self._load_local)

    async def _load_local(self) -> None:
        try:
            await self.app.load_local_files(Path.home())
        except Exception:
            pass
