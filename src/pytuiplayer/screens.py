"""Screens for radio and local playback modes.

The app switches between ``RadioScreen`` and ``LocalScreen`` via
``switch_screen`` instead of manually toggling widget visibility, giving a
clean mode-switch abstraction. Each screen composes the shared widgets
(Header, Footer, NowPlaying, controls) plus its mode-specific
content.

Winamp-style layout:
  ┌─────────────────────────────────────────────────────┐
  │ Header (app name + key hints)                       │
  ├─────────────────────────────────────────────────────┤
  │ NowPlaying (LED display + seek bar)                 │
  ├─────────────────────────────────────────────────────┤
  │ Controls (Play/Pause/Stop/Prev/Next/Volume)         │
  ├────────────┬────────────────────────────────────────┤
  │ Sidebar    │ Content (station list or local list)    │
  │ (Mode      │ + search bar for local mode             │
  │  buttons)  │                                        │
  ├────────────┴────────────────────────────────────────┤
  │ Footer (key hints)                                  │
  └─────────────────────────────────────────────────────┘
"""

from pathlib import Path

from textual import on
from textual.containers import Horizontal, Vertical
from textual.events import Key
from textual.screen import Screen
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    RadioButton,
    RadioSet,
    Static,
)

from pytuiplayer.widgets import NowPlaying, VolumeIndicator


class ModeScreen(Screen):
    """Base class for mode screens — composes shared + mode-specific widgets.

    Winamp-style layout:
      - NowPlaying: full-width LED display with integrated seek bar
      - Controls: horizontal button bar
      - Main content: sidebar (mode selector) + content area
    """

    def compose(self):
        yield Header()
        yield Footer()
        # Now Playing display — full width, LED style with integrated seek bar
        yield NowPlaying(id="now-playing")
        # Controls bar
        with Horizontal(id="controls"):
            yield Button("⏮", id="prev", classes="control-btn")
            yield Button("▶", id="play", classes="control-btn")
            yield Button("⏸", id="pause", classes="control-btn")
            yield Button("⏹", id="stop", classes="control-btn")
            yield Button("⏭", id="next", classes="control-btn")
            yield VolumeIndicator(id="volume-indicator")

        # Main content area
        with Horizontal(id="main-content"):
            with Vertical(id="sidebar") as sidebar:
                yield RadioSet(
                    RadioButton("Radio", id="radio-option", value=self._radio_value),
                    RadioButton("Local", id="local-option", value=not self._radio_value),
                    id="option-set",
                )
                sidebar.border_title = "Mode"

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
    """Local mode: directory tree + local file list + search bar with mode selector.

    Winamp-style:
      - Search input at top of content area (type to filter)
      - DirectoryTree for browsing
      - ListView for results
      - Loading indicator during file scan
    """

    @property
    def _radio_value(self) -> bool:
        return False

    def compose_mode_content(self):
        yield Static("🔍 Search:", id="search-label")
        yield Input(placeholder="Type to filter tracks...", id="search-input")
        yield DirectoryTree(self._default_music_dir(), id="directory-tree")
        yield Static("", id="loading-status")
        yield ListView(id="local-list")

    @staticmethod
    def _default_music_dir() -> str:
        """Prefer ~/Music for browsing; fall back to $HOME if it doesn't exist."""
        music = Path.home() / "Music"
        try:
            if music.is_dir():
                return str(music)
        except Exception:
            pass
        return str(Path.home())

    def on_mount(self) -> None:
        super().on_mount()
        local_list = self.query_one("#local-list", ListView)
        local_list.border_title = "Local Music"
        # Defer local file loading to avoid race condition with M3U loading.
        # The timer is stored so it can be cancelled if an M3U is loaded first.
        self._pending_local_load = self.set_timer(0.1, self._load_local)
        # Debounce timer for search input (None = no pending search)
        self._search_pending = None

    async def _load_local(self) -> None:
        """Load local files. Status messages handled by load_local_files itself."""
        try:
            await self.app.playlist_loader.load_local_files(Path(self._default_music_dir()))
        except Exception:
            try:
                loading = self.app.query_one("#loading-status", Static)
                loading.update("❌ Error loading files")
            except Exception:
                pass

    def cancel_pending_local_load(self) -> None:
        """Cancel the pending local file load (called when loading an M3U)."""
        if hasattr(self, '_pending_local_load') and self._pending_local_load:
            self._pending_local_load.stop()
            self._pending_local_load = None

    @on(Input.Changed, "#search-input")
    async def on_search_changed(self, event: Input.Changed) -> None:
        """Debounced search: filter local list after typing pauses (~150ms)."""
        # Cancel any pending search from a previous keystroke
        if self._search_pending:
            self._search_pending.stop()
        # Schedule a new search after the debounce window
        self._search_pending = self.set_timer(0.15, self._run_debounced_search)

    async def _run_debounced_search(self) -> None:
        """Called after debounce timer fires — execute the actual search."""
        self._search_pending = None
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.lower().strip()
        local_list = self.query_one("#local-list", ListView)
        await self._filter_local_list(local_list, query)

    @on(Input.Submitted, "#search-input")
    async def on_search_submitted(self, event: Input.Submitted) -> None:
        """Enter key in search: blur input to restore keyboard bindings."""
        self.query_one("#search-input", Input).blur()

    async def on_key(self, event: Key) -> None:
        """Handle Escape key to blur search input and restore keyboard bindings."""
        if event.key == "escape":
            search_input = self.query_one("#search-input", Input)
            if search_input.has_focus:
                search_input.blur()
                # Clear search to restore full list
                search_input.value = ""
                local_list = self.query_one("#local-list", ListView)
                await self._filter_local_list(local_list, "")
                event.prevent_default()

    def _resolve_search_results(self, query: str, all_items: dict) -> list:
        """Resolve which items match the query.

        Strategy:
        1. If metadata_index has data → use FTS5 full-text search across
           artist/album/title/genre, then intersect results with loaded items.
        2. Otherwise → fall back to linear title substring scan.

        Returns list of item_data dicts matching the query.
        """
        metadata_index = getattr(self.app, "metadata_index", None)
        if metadata_index and metadata_index.get_track_count() > 0:
            try:
                fts_results = metadata_index.search_tracks(query)
                if fts_results:
                    # Build set of FTS-matched paths for fast lookup
                    fts_paths = {r["path"] for r in fts_results}
                    # Intersect: only items both loaded AND matched by FTS
                    matched = []
                    for item_data in all_items.values():
                        src = item_data.get("source") if isinstance(item_data, dict) else None
                        if src is None:
                            continue
                        # Match by stringified source path
                        if str(src) in fts_paths:
                            matched.append(item_data)
                    return matched
            except Exception:
                # FTS failure — fall through to linear scan
                pass

        # Fallback: linear title substring scan (no index or FTS failed)
        matched = []
        for item_data in all_items.values():
            if isinstance(item_data, dict):
                title_text = item_data.get("title", "")
            else:
                title_text = getattr(item_data, "title", "")
            if query in str(title_text).lower():
                matched.append(item_data)
        return matched

    async def _filter_local_list(self, local_list: ListView, query: str) -> None:
        """Filter the local list to show only items matching the query.

        Uses FTS5 when metadata index is available, otherwise falls back to
        linear title substring scan.
        Rebuilds fresh ListItems from stored data to avoid blank entries
        that occur when reusing detached widgets after clear()+mount().
        """
        import asyncio

        from pytuiplayer.utils import fmt_mmss

        all_items = getattr(self.app, "local_items", {})
        if not all_items:
            return

        # Normalize query (lowercase, strip)
        query = query.lower().strip() if query else ""

        # Determine which items to show (FTS or fallback)
        if not query:
            items_to_show = list(all_items.values())
        else:
            items_to_show = self._resolve_search_results(query, all_items)

        # Clear and rebuild based on filter
        # First, create all new items
        new_items = []
        for item_data in items_to_show:
            if isinstance(item_data, dict):
                title = item_data.get("title", "")
                duration = item_data.get("duration")
            else:
                title = getattr(item_data, "title", "")
                duration = getattr(item_data, "duration", None)

            duration_str = fmt_mmss(duration) if duration is not None else ""
            display = f"{title:<40} {duration_str}"
            # Pass Label to constructor - this is the reliable way
            item = ListItem(Label(display))
            item.data = item_data
            new_items.append(item)

        # Remove old children and await completion
        await local_list.remove_children()
        # Yield to let Textual complete the removal
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await asyncio.sleep(0)

        # Mount all new items at once
        await local_list.mount(*new_items)


