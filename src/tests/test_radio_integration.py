"""Integration test: run the real TUI headless and start a radio stream.

This exercises the same code path a user triggers by selecting a station and
pressing play. The app runs inside Textual's virtual test harness (no real
terminal/TTY needed) and mpv is routed to a null audio sink so it does not try
to open a sound card on a headless box.

The test requires network access to a live stream, so it is skipped automatically
when no reachable station URL is found (e.g. in offline CI). Set
PYTUIP_RADIO_TEST=1 to force it to run even if network probes fail.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import urllib.request
from pathlib import Path

import pytest

# --- Route mpv to a null audio sink so it works without a sound card ---
_MPV_HOME = tempfile.mkdtemp(prefix="pytuiplayer-mpv-")
Path(_MPV_HOME, "mpv.conf").write_text("ao=null\nno-video=yes\n", encoding="utf-8")
os.environ["MPV_HOME"] = _MPV_HOME

from pytuiplayer.tui_app import MusicPlayerApp  # noqa: E402


def _reachable_station(app: MusicPlayerApp):
    """Return (index, station) for the first station whose URL is reachable, else None."""
    for idx, station in enumerate(app.stations.stations):
        url = station.get("url", "")
        if not url.startswith(("http://", "https://")):
            continue
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"Icy-MetaData": "1"})
            urllib.request.urlopen(req, timeout=5)
            return idx, station
        except Exception:
            continue
    return None


@pytest.mark.network
def test_radio_starts_stream_and_updates_now_playing():
    async def _run():
        app = MusicPlayerApp()
        async with app.run_test() as pilot:
            # on_mount loads stations; give the async load a tick to finish.
            await pilot.pause()
            await asyncio.sleep(0.3)

            if not app.stations or not app.stations.stations:
                pytest.skip("no stations loaded")

            picked = _reachable_station(app)
            if picked is None and not os.getenv("PYTUIP_RADIO_TEST"):
                pytest.skip("no reachable radio stream (offline?)")

            idx, station = picked if picked is not None else (0, app.stations.stations[0])

            await app.play_station(station, idx)
            await pilot.pause()
            await asyncio.sleep(6.0)  # let mpv connect + receive ICY metadata

            # Inspect the live mpv backend to confirm it really connected.
            player = app.mpv.player
            try:
                active = getattr(player, "path", None)
            except Exception:
                active = None

            assert getattr(app, "currently_playing", None) == "radio"
            connected = bool(active) and str(active).startswith(("http://", "https://"))
            assert connected, f"mpv did not connect to a stream URL (path={active!r})"

            app.action_stop()
            await pilot.pause()

    asyncio.run(_run())
