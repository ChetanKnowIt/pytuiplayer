#!/usr/bin/env python3
"""Report release-cadence status for pytuiplayer.

Discipline (ROADMAP.md "Release Cadence Policy"): cut a release every 3 merged
feature branches. This script derives the *merged* `feature/*` branches from git
history and compares that count to the last release recorded in
`docs/RELEASE_CADENCE.md`, printing how many features remain until the next
release is due.

It is a sanity check only — the ledger in the doc is authoritative. The git
count can drift (e.g. a feature branch force-pushed, renamed, or merged via
squash without a `feature/` prefix), so the doc is the source of truth.

Usage:
    uv run python scripts/release_cadence.py
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER = REPO_ROOT / "docs" / "RELEASE_CADENCE.md"
FEATURES_PER_RELEASE = 3
RELEASE_RE = re.compile(r"v(\d+)\.(\d+)\.(\d+)\b")


def merged_feature_branches() -> list[str]:
    """Return merged `feature/*` branch names seen in git history (deduped, ordered)."""
    # --merged main: branches already in main's history.
    try:
        out = subprocess.run(
            ["git", "branch", "-r", "--merged", "main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        # Fall back to local main if remote tracking is unavailable.
        out = subprocess.run(
            ["git", "branch", "--merged", "main"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    names: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        name = line.strip().removeprefix("*").strip()
        name = re.sub(r"^origin/", "", name)
        if name.startswith("feature/") and name not in seen:
            seen.add(name)
            names.append(name)
    return names


def last_release_from_ledger() -> tuple[tuple[int, int, int], int] | None:
    """Return (version tuple, features-since-last-release) from the ledger, or None.

    The highest semantic version found in the ledger wins. `features since last
    release:` (if present) is the authoritative counter.
    """
    if not LEDGER.exists():
        return None
    text = LEDGER.read_text(encoding="utf-8")
    last_ver = None
    last_count = None
    for line in text.splitlines():
        # Only count versions that appear in the Releases table (rows start with "| v").
        if line.lstrip().startswith("| v"):
            m = RELEASE_RE.search(line)
            if m:
                ver = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
                if last_ver is None or ver > last_ver:
                    last_ver = ver
        cm = re.search(r"features since last release:\s*(\d+)", line, re.IGNORECASE)
        if cm:
            last_count = int(cm.group(1))
    if last_ver is None:
        return None
    return last_ver, last_count if last_count is not None else 0


def main() -> int:
    branches = merged_feature_branches()
    ledger = last_release_from_ledger()

    print(f"Merged feature/* branches in git history (soft hint, branches are "
          f"often deleted after merge): {len(branches)}")
    for b in branches:
        print(f"  - {b}")

    if ledger is None:
        print("\nNo release recorded in docs/RELEASE_CADENCE.md yet.")
        print("Next release: v0.1.0 (baseline) is the reference; cadence starts after it.")
        return 0

    last_ver, since = ledger
    due = since >= FEATURES_PER_RELEASE
    print(
        f"\nLast release: v{last_ver[0]}.{last_ver[1]}.{last_ver[2]} "
        f"| features since last release (ledger, authoritative): {since}/{FEATURES_PER_RELEASE}"
    )
    if due:
        next_minor = last_ver[1] + 1
        print(f"RELEASE DUE -> tag v{last_ver[0]}.{next_minor}.0 on main to publish.")
    else:
        print(f"Next release (v{last_ver[0]}.{last_ver[1] + 1}.0) due after "
              f"{FEATURES_PER_RELEASE - since} more merged feature branch(es).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
