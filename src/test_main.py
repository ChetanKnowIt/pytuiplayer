# main.py
from pytuiplayer.tui_app import MusicPlayerApp


def main() -> int:
    """Programmatic entrypoint for tests and CLI.

    Returns an exit code integer (0 on success).
    """
    app = MusicPlayerApp()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


