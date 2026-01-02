from pathlib import Path


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
