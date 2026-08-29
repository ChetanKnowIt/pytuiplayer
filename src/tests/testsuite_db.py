"""SQLite-backed test inventory for pytuiplayer.

The verbose per-file test inventory that used to live in ROADMAP.md is now
stored in a small, structured SQLite database (``testsuite.db`` at the repo
root). This keeps ROADMAP.md light and makes the inventory queryable / reusable
as features are added.

Design
------
* The database is a *cache of the last pytest run*, not a source of truth.
  Every ``uv run pytest`` run refreshes it (see ``conftest.py`` hooks), and the
  standalone ``scripts/update_testsuite_db.py`` can rebuild it manually.
* Schema (idempotent upserts on the natural key ``(file, name)``):

    files(file, description, line_count)            -- one row per test module
    tests(name, file, description, line, markers)   -- one row per test function
    runs(id, started_at, pytest_exit, collected, passed, failed, skipped,
         errors, duration_s, branch, python_version, note)
    backlog(name, kind, description, status, source)  -- ROADMAP Test Backlog mirror

* ``meta`` stores lightweight key/value settings (e.g. last-write timestamp).

All functions are stdlib-only (``sqlite3``, ``pathlib``, ``datetime``,
``json``) so they work under ``uv run`` without extra dependencies.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB = REPO_ROOT / "testsuite.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file        TEXT PRIMARY KEY,
    description TEXT NOT NULL DEFAULT '',
    line_count  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tests (
    name        TEXT NOT NULL,
    file        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    line        INTEGER NOT NULL DEFAULT 0,
    markers     TEXT NOT NULL DEFAULT '',           -- JSON array of marker names
    PRIMARY KEY (file, name),
    FOREIGN KEY (file) REFERENCES files(file)
);

CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    pytest_exit  INTEGER NOT NULL,
    collected    INTEGER NOT NULL DEFAULT 0,
    passed       INTEGER NOT NULL DEFAULT 0,
    failed       INTEGER NOT NULL DEFAULT 0,
    skipped      INTEGER NOT NULL DEFAULT 0,
    errors       INTEGER NOT NULL DEFAULT 0,
    duration_s   REAL NOT NULL DEFAULT 0.0,
    branch       TEXT NOT NULL DEFAULT '',
    python_version TEXT NOT NULL DEFAULT '',
    note         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS backlog (
    name        TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,          -- 'unit' | 'integration'
    description TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'pending',  -- 'done' | 'pending'
    source      TEXT NOT NULL DEFAULT '' -- e.g. 'ROADMAP Test Backlog #2'
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tests_file ON tests(file);
CREATE INDEX IF NOT EXISTS idx_backlog_status ON backlog(status);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open (and initialise) the database, returning a connection."""
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def upsert_file(conn, file: str, description: str = "", line_count: int = 0) -> None:
    """Insert or update the per-module row in ``files``."""
    conn.execute(
        "INSERT INTO files(file, description, line_count) VALUES(?, ?, ?) "
        "ON CONFLICT(file) DO UPDATE SET "
        "description=excluded.description, line_count=excluded.line_count",
        (file, description, line_count),
    )


def clear_tests_for_file(conn, file: str) -> None:
    """Remove test rows for a single module (used on a refresh run)."""
    conn.execute("DELETE FROM tests WHERE file = ?", (file,))


def ensure_file(conn, file: str) -> None:
    """Insert a file row only if it does not already exist (never overwrites
    descriptions set by the richer manual updater)."""
    conn.execute(
        "INSERT OR IGNORE INTO files(file, description, line_count) VALUES(?, '', 0)",
        (file,),
    )


def upsert_test(
    conn,
    name: str,
    file: str,
    description: str = "",
    line: int = 0,
    markers: list[str] | None = None,
) -> None:
    """Insert or update a single test row (key = (file, name))."""
    conn.execute(
        "INSERT INTO tests(name, file, description, line, markers) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(file, name) DO UPDATE SET "
        "description=excluded.description, line=excluded.line, markers=excluded.markers",
        (name, file, description, line, json.dumps(markers or [])),
    )


def record_run(
    conn,
    pytest_exit: int,
    collected: int = 0,
    passed: int = 0,
    failed: int = 0,
    skipped: int = 0,
    errors: int = 0,
    duration_s: float = 0.0,
    branch: str = "",
    python_version: str = "",
    note: str = "",
) -> int:
    """Append a run record and return its row id."""
    cur = conn.execute(
        "INSERT INTO runs(started_at, pytest_exit, collected, passed, failed, "
        "skipped, errors, duration_s, branch, python_version, note) "
        "VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            now_iso(),
            pytest_exit,
            collected,
            passed,
            failed,
            skipped,
            errors,
            duration_s,
            branch,
            python_version,
            note,
        ),
    )
    return int(cur.lastrowid)


def upsert_backlog(
    conn,
    name: str,
    kind: str,
    description: str = "",
    status: str = "pending",
    source: str = "",
) -> None:
    """Insert or update a ROADMAP backlog row."""
    conn.execute(
        "INSERT INTO backlog(name, kind, description, status, source) "
        "VALUES(?, ?, ?, ?, ?) "
        "ON CONFLICT(name) DO UPDATE SET "
        "kind=excluded.kind, description=excluded.description, "
        "status=excluded.status, source=excluded.source",
        (name, kind, description, status, source),
    )


def count_lines(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def discover_tests(root: Path | None = None) -> list[dict]:
    """Walk ``src/tests`` and return one dict per test module with its test count
    and line count. Used by the manual updater to enrich ``files`` rows."""
    base = Path(root) if root else (REPO_ROOT / "src" / "tests")
    out = []
    for p in sorted(base.glob("test_*.py")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        n_tests = text.count("def test_")
        out.append(
            {
                "file": p.resolve()
                .relative_to(REPO_ROOT)
                .as_posix(),
                "line_count": count_lines(p),
                "test_count": n_tests,
            }
        )
    return out


def summary(conn) -> dict:
    """Return aggregate counts for quick reporting."""
    t = conn.execute("SELECT COUNT(*) FROM tests").fetchone()[0]
    f = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    b_total = conn.execute("SELECT COUNT(*) FROM backlog").fetchone()[0]
    b_done = conn.execute("SELECT COUNT(*) FROM backlog WHERE status='done'").fetchone()[0]
    last = conn.execute(
        "SELECT started_at, pytest_exit, collected, passed, failed, skipped, errors, "
        "duration_s, branch FROM runs ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return {
        "tests": t,
        "files": f,
        "backlog_total": b_total,
        "backlog_done": b_done,
        "last_run": last,
    }
