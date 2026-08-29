#!/usr/bin/env python3
"""Pretty-print the pytuiplayer test inventory stored in ``testsuite.db``.

The verbose per-file inventory used to live in ROADMAP.md. It now lives in a
SQLite database refreshed by ``uv run pytest`` (via conftest.py) and enriched by
``scripts/update_testsuite_db.py``. This script renders that DB as a report.

Usage:
    uv run python scripts/report_testsuite_db.py
    uv run python scripts/report_testsuite_db.py --db /path/to/testsuite.db
    uv run python scripts/report_testsuite_db.py --by-file
    uv run python scripts/report_testsuite_db.py --backlog
    uv run python scripts/report_testsuite_db.py --last-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "tests"))

from testsuite_db import REPO_ROOT, connect, summary  # noqa: E402


def _print_table(headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    print(line)
    print("-" * len(line))
    for row in rows:
        print("  ".join(str(c).ljust(widths[i]) for i, c in enumerate(row)))


def cmd_summary(conn) -> None:
    s = summary(conn)
    last = s["last_run"]
    print("== Test Inventory Summary ==")
    print(f"  test functions : {s['tests']}")
    print(f"  test modules   : {s['files']}")
    print(f"  backlog total  : {s['backlog_total']}  (done: {s['backlog_done']})")
    if last:
        (
            started_at,
            pytest_exit,
            collected,
            passed,
            failed,
            skipped,
            errors,
            duration_s,
            branch,
        ) = last
        print("  last run       : " + started_at)
        print(f"    exit={pytest_exit} collected={collected} "
              f"passed={passed} failed={failed} skipped={skipped} errors={errors} "
              f"duration={duration_s:.1f}s branch={branch}")


def cmd_by_file(conn) -> None:
    print("== Tests by module ==")
    rows = conn.execute(
        "SELECT f.file, f.description, f.line_count, COUNT(t.name) AS n "
        "FROM files f LEFT JOIN tests t ON t.file = f.file "
        "GROUP BY f.file ORDER BY f.file"
    ).fetchall()
    _print_table(
        ["file", "description", "lines", "tests"],
        [[r[0], r[1], str(r[2]), str(r[3])] for r in rows],
    )

    # Detailed test list per file
    print("\n== Test functions ==")
    tests = conn.execute(
        "SELECT name, file, line, markers FROM tests ORDER BY file, line"
    ).fetchall()
    for name, file, line, markers in tests:
        m = json.loads(markers or "[]")
        mtag = f" [{','.join(m)}]" if m else ""
        print(f"  {file}:{line}  {name}{mtag}")


def cmd_backlog(conn) -> None:
    print("== ROADMAP Test Backlog ==")
    rows = conn.execute(
        "SELECT name, kind, status, source FROM backlog ORDER BY "
        "CASE kind WHEN 'unit' THEN 0 ELSE 1 END, name"
    ).fetchall()
    _print_table(
        ["name", "kind", "status", "source"],
        [[r[0], r[1], r[2], r[3]] for r in rows],
    )
    done = sum(1 for r in rows if r[2] == "done")
    print(f"\n  {done}/{len(rows)} backlog items marked done")


def cmd_last_run(conn) -> None:
    print("== Recent runs ==")
    rows = conn.execute(
        "SELECT id, started_at, pytest_exit, collected, passed, failed, "
        "skipped, errors, duration_s, branch FROM runs ORDER BY id DESC LIMIT 10"
    ).fetchall()
    _print_table(
        ["id", "started_at", "exit", "col", "pass", "fail", "skip", "err", "sec", "branch"],
        [
            [str(r[0]), r[1], str(r[2]), str(r[3]), str(r[4]), str(r[5]),
             str(r[6]), str(r[7]), f"{r[8]:.1f}", r[9]]
            for r in rows
        ],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(REPO_ROOT / "testsuite.db"), help="DB path")
    parser.add_argument("--by-file", action="store_true", help="List tests per module")
    parser.add_argument("--backlog", action="store_true", help="Show backlog table")
    parser.add_argument("--last-run", action="store_true", help="Show recent run records")
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: {db_path} not found. Run `uv run pytest` or "
              f"scripts/update_testsuite_db.py first.", file=sys.stderr)
        return 1

    conn = connect(db_path)
    try:
        # Default: print the summary plus everything when no selector is given.
        if not (args.by_file or args.backlog or args.last_run):
            cmd_summary(conn)
            print()
            cmd_by_file(conn)
            print()
            cmd_backlog(conn)
            print()
            cmd_last_run(conn)
        else:
            if args.by_file:
                cmd_by_file(conn)
            if args.backlog:
                cmd_backlog(conn)
            if args.last_run:
                cmd_last_run(conn)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
