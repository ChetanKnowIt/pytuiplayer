"""Volume control for pytuiplayer.

Handles volume up/down/mute actions and updates the VolumeIndicator widget.
"""

from pytuiplayer.logging_config import get_logger
from pytuiplayer.profiling import profile
from pytuiplayer.widgets import VolumeIndicator

logger = get_logger("volume")


class VolumeController:
    """Manages volume state and updates the VolumeIndicator widget."""

    def __init__(self, app):
        self.app = app

    @profile
    def update_volume_ui(self):
        """Sync volume/mute state to the VolumeIndicator widget."""
        try:
            vol = self.app.query_one("#volume-indicator", VolumeIndicator)
            vol.volume = self.app.volume
            vol.muted = self.app.muted
        except Exception:
            logger.debug("update_volume_ui failed", exc_info=True)

    @profile
    def action_volume_up(self):
        """Increase volume by 5, unmuting if muted."""
        self.app.volume = min(100, getattr(self.app, "volume", 50) + 5)
        if self.app.muted:
            self.app.muted = False
        try:
            self.app.mpv.set_volume(self.app.volume)
        except Exception:
            logger.warning("set_volume failed", exc_info=True)
        self.update_volume_ui()

    @profile
    def action_volume_down(self):
        """Decrease volume by 5, muting at 0."""
        self.app.volume = max(0, getattr(self.app, "volume", 50) - 5)
        if self.app.volume == 0:
            self.app.muted = True
        else:
            self.app.muted = False
        try:
            self.app.mpv.set_volume(self.app.volume)
        except Exception:
            logger.warning("set_volume failed", exc_info=True)
        self.update_volume_ui()

    @profile
    def action_toggle_mute(self):
        """Toggle mute, restoring previous volume on unmute."""
        if not getattr(self.app, "muted", False):
            self.app._prev_volume = getattr(self.app, "volume", 50)
            self.app.muted = True
            try:
                self.app.mpv.set_volume(0)
            except Exception:
                logger.warning("set_volume(0) failed", exc_info=True)
        else:
            self.app.muted = False
            self.app.volume = getattr(self.app, "_prev_volume", 50)
            try:
                self.app.mpv.set_volume(self.app.volume)
            except Exception:
                logger.warning("set_volume failed", exc_info=True)
        self.update_volume_ui()
