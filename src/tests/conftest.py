from pathlib import Path

import pytest


def pytest_ignore_collect(collection_path: Path):
    """Ignore interactive/manual test scripts that require user input or long-running streams.

    Newer pytest versions pass a pathlib.Path as `collection_path`.
    """
    ignore = {
        "test_mpv.py",
        "test_pyradio.py",
        "test_raw_mpv.py",
        "test_main.py",
    }
    try:
        return collection_path.name in ignore
    except Exception:
        return False


# ---------------------------------------------------------------------------
# testsuite.db integration
#
# On every `uv run pytest` run we refresh the SQLite test inventory
# (testsuite.db) so the backlog dashboard stays in sync with the code. This is
# best-effort: any failure here is logged but never fails the suite.
# ---------------------------------------------------------------------------
_RUN_COUNTS: dict[str, int] = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}


def pytest_sessionstart(session: pytest.Session) -> None:
    _RUN_COUNTS.update(passed=0, failed=0, skipped=0, error=0)


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.skipped:
        _RUN_COUNTS["skipped"] += 1
    elif report.failed:
        _RUN_COUNTS["failed" if report.when == "call" else "error"] += 1
    else:
        _RUN_COUNTS["passed"] += 1


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    try:
        from testsuite_db import connect, ensure_file, record_run, upsert_test

        conn = connect()
        try:
            # Refresh each test row encountered this run (key = (file, name)).
            for item in session.session.items:
                try:
                    fspath = getattr(item, "path", None) or getattr(item, "fspath", None)
                    if fspath is None:
                        continue
                    rel = (
                        Path(fspath)
                        .resolve()
                        .relative_to(Path(__file__).resolve().parent.parent.parent)
                        .as_posix()
                    )
                    ensure_file(conn, rel)
                    name = item.name
                    markers = sorted(
                        m.name
                        for m in getattr(item, "iter_markers", lambda: [])()
                        if hasattr(m, "name")
                    )
                    # item.location is (file, lineno, testname); lineno is 0-based.
                    loc = getattr(item, "location", None)
                    line = int((loc[1] + 1) if loc else (getattr(item, "line", 0) or 0))
                    upsert_test(conn, name=name, file=rel, line=line, markers=markers)
                except Exception:
                    continue

            # Gather run metadata (git branch + python version) for the run record.
            branch = ""
            try:
                import subprocess

                branch = (
                    subprocess.run(
                        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                        cwd=Path(__file__).resolve().parent.parent.parent,
                        capture_output=True,
                        text=True,
                        timeout=5,
                    ).stdout.strip()
                    or ""
                )
            except Exception:
                branch = ""

            pyver = ""
            try:
                import platform

                pyver = platform.python_version()
            except Exception:
                pyver = ""

            record_run(
                conn,
                pytest_exit=int(exitstatus),
                collected=int(getattr(session, "testscollected", 0) or 0),
                passed=_RUN_COUNTS["passed"],
                failed=_RUN_COUNTS["failed"],
                skipped=_RUN_COUNTS["skipped"],
                errors=_RUN_COUNTS["error"],
                duration_s=float(getattr(session, "testsduration", 0.0) or 0.0),
                branch=branch,
                python_version=pyver,
                note="auto-updated by pytest run (conftest hook)",
            )
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # pragma: no cover - never break the test run
        print(f"[testsuite.db] WARNING: failed to update inventory: {exc}")
