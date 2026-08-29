def main() -> None:
    """Console-script entry point: launch the real Textual TUI.

    The heavy import is deferred to call time so `import pytuiplayer` stays cheap
    and the editable install (which does not expose ``pytuiplayer.__main`` as an
    importable submodule) still resolves the script target. ``python -m pytuiplayer``
    reaches the same launcher via ``pytuiplayer/__main__.py``.
    """
    from pytuiplayer.tui_app import MusicPlayerApp

    MusicPlayerApp().run()
