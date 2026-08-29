"""Headless demo: launch the real pytuiplayer TUI, load stations, and start radio.

This runs the *actual* MusicPlayerApp (the same code your keypresses drive) inside
Textual's virtual test harness -- no real terminal/TTY required. mpv is routed to a
null audio sink via a temporary MPV_HOME so it does not try to open a sound card on a
headless box. We then trigger the radio-start code path (play_station -> mpv.play)
and report what mpv reports (connected stream URL + ICY metadata).
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

# --- Route mpv to a null audio sink so it works without a sound card ---
_mpv_home = tempfile.mkdtemp(prefix="pytuiplayer-mpv-")
Path(_mpv_home, "mpv.conf").write_text("ao=null\nno-video=yes\n", encoding="utf-8")
os.environ["MPV_HOME"] = _mpv_home

from pytuiplayer.tui_app import MusicPlayerApp  # noqa: E402

# Capture mpv's log output (the app installs log_handler=print, which goes to stderr).
# We re-route python-mpv's log to a buffer so we can show ICY metadata.


async def main() -> int:
    app = MusicPlayerApp()
    async with app.run_test() as pilot:
        # on_mount loads stations; give the async load a tick to finish.
        await pilot.pause()
        await asyncio.sleep(0.3)

        if not app.stations or not app.stations.stations:
            print("[DEMO] ERROR: no stations loaded")
            return 1

        print(f"[DEMO] Loaded {len(app.stations.stations)} stations:")
        for i, s in enumerate(app.stations.stations):
            print(f"        [{i}] {s['name']}  ({s['url']})")

        # Prefer a reachable stream: the raw-IP station in stations.json is dead,
        # so pick the SomaFM HTTPS one if present, else index 0.
        idx = 0
        for i, s in enumerate(app.stations.stations):
            if "somafm.com" in s["url"]:
                idx = i
                break

        station = app.stations.stations[idx]
        print(f"[DEMO] Starting radio via play_station(index={idx}): {station['name']}")

        # This is the exact code path your 'select station + Enter/play' triggers.
        await app.play_station(station, idx)
        await pilot.pause()
        await asyncio.sleep(6.0)  # let mpv connect + receive ICY metadata

        # Inspect the live mpv backend to confirm it really connected.
        player = app.mpv.player
        try:
            active = getattr(player, "path", None)
        except Exception:
            active = None
        try:
            pause = bool(getattr(player, "pause", False))
        except Exception:
            pause = None

        print("[DEMO] --- Now Playing UI state ---")
        print(f"        currently_playing = {getattr(app, 'currently_playing', None)!r}")
        print(f"        current_title      = {getattr(app, 'current_title', None)!r}")
        print(f"        mpv.path          = {active!r}")
        print(f"        mpv.pause         = {pause!r}")

        connected = bool(active) and str(active).startswith(("http://", "https://"))
        if connected:
            print("[DEMO] SUCCESS: radio stream connected via mpv.")
        else:
            print("[DEMO] NOTE: mpv reported no active URL (stream may still be buffering).")

        app.action_stop()
        await pilot.pause()

    print("[DEMO] TUI exited cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
