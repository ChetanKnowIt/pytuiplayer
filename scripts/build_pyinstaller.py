#!/usr/bin/env python3
"""Build a one-file PyInstaller executable for pytuiplayer.

Usage:
    uv run python scripts/build_pyinstaller.py

The app resolves its data files (``stations.json``, ``musicplayer_tui.css``) at
runtime via ``Path(__file__).parent``. Both are bundled into the package
directory inside the frozen executable so that path still resolves after
extraction. Textual and python-mpv are pulled in with ``--collect-all`` so their
data files / shared-object hooks are included.

OUTPUT
    dist/pytuiplayer            (Linux / macOS)
    dist/pytuiplayer.exe        (Windows)

RUNTIME REQUIREMENT
    python-mpv loads the *system* libmpv shared library (libmpv.so / mpv-2.dll)
    at runtime via ctypes. That library is NOT bundled by PyInstaller, so the
    target machine must have ``mpv`` installed and on PATH for playback to work.
"""

from __future__ import annotations

import os
import sys

from PyInstaller import __main__ as pyi_main

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "src")
PKG = os.path.join(SRC, "pytuiplayer")
ENTRY = os.path.join(PKG, "__main__.py")

# (source file, destination dir inside the bundle). The destination must match
# Path(__file__).parent at runtime, i.e. the package directory "pytuiplayer".
DATAS = [
    (os.path.join(PKG, "stations.json"), "pytuiplayer"),
    (os.path.join(PKG, "musicplayer_tui.css"), "pytuiplayer"),
]


def main() -> int:
    if not os.path.exists(ENTRY):
        print(f"[build] entry point not found: {ENTRY}", file=sys.stderr)
        return 1

    argv = [
        ENTRY,
        "--onefile",
        "--console",
        "--name",
        "pytuiplayer",
        "--paths",
        SRC,
        "--noconfirm",
        "--clean",
        # Pull in data files + hidden imports for the heavy GUI / binding deps.
        "--collect-all",
        "textual",
        "--collect-all",
        "mpv",
    ]
    for src, dest in DATAS:
        argv += ["--add-data", f"{src}{os.pathsep}{dest}"]

    print(f"[build] pyinstaller {' '.join(argv)}")
    pyi_main.run(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
