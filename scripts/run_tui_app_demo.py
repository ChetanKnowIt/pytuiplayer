"""Headless demo: launch the real pytuiplayer TUI and assert it boots + renders.

This is the counterpart to ``run_radio_demo.py`` but exercises the *base* launch
path -- the same code ``uv run pytuiplayer`` (and ``python -m pytuiplayer``) drives.
It runs ``MusicPlayerApp`` inside Textual's virtual test harness (no real
terminal/TTY required) and confirms:

  * the app mounts without error,
  * stations load from ``stations.json``,
  * the rendered UI contains the "Music Player" title and a Now Playing widget.

mpv is routed to a null audio sink so it does not try to open a sound card on a
headless box (the demo does not start playback).
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path

# --- Route mpv to a null audio sink so it works without a sound card ---
_MPV_HOME = tempfile.mkdtemp(prefix="pytuiplayer-mpv-")
Path(_MPV_HOME, "mpv.conf").write_text("ao=null\nno-video=yes\n", encoding="utf-8")
os.environ["MPV_HOME"] = _MPV_HOME

from pytuiplayer.tui_app import MusicPlayerApp  # noqa: E402


async def main() -> int:
    app = MusicPlayerApp()
    async with app.run_test() as pilot:
        # on_mount loads stations; give the async load a tick to finish.
        await pilot.pause()
        await asyncio.sleep(0.5)

        # 1) app mounted and stations loaded
        if not app.stations or not app.stations.stations:
            print("[DEMO] ERROR: no stations loaded after mount")
            return 1
        print(f"[DEMO] Mounted OK; loaded {len(app.stations.stations)} stations.")

        # 2) the app title is set (compose defines the window title "Music Player")
        print(f"[DEMO] app.title = {app.title!r}")

        # 3) the NowPlaying widget renders and reflects the idle state
        try:
            now = app.query_one("NowPlaying")
        except Exception:
            now = None
        if now is None:
            print("[DEMO] ERROR: NowPlaying widget not found in DOM")
            return 1

        rendered = now.render()
        print(f"[DEMO] NowPlaying.render() -> {rendered!r}")

        # 4) the app booted and rendered the expected top-level UI:
        #    - window title is "Music Player" (set in on_mount)
        #    - NowPlaying reflects the idle "Nothing playing" state
        ok = (app.title == "Music Player") and (
            "Nothing playing" in rendered or "Now Playing" in rendered
        )
        if not ok:
            print("[DEMO] ERROR: expected 'Music Player' title / Now Playing widget not rendered")
            return 1

        print("[DEMO] SUCCESS: TUI booted and rendered the main UI.")
        return 0

    print("[DEMO] TUI exited cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
