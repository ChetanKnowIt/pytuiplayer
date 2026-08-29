def test_main_calls_run(monkeypatch):
    import pytuiplayer.__main__ as entrypoint

    called = {}

    class FakeApp:
        def __init__(self):
            called["constructed"] = True

        def run(self):
            called["run"] = True

    # Replace MusicPlayerApp in the module under test
    monkeypatch.setattr(entrypoint, "MusicPlayerApp", FakeApp)

    # Call main and assert it returns 0 and called run
    assert entrypoint.main() == 0
    assert called.get("run") is True
