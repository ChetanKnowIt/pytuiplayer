def test_main_calls_run(monkeypatch):
    import test_main

    called = {}

    class FakeApp:
        def __init__(self):
            called['constructed'] = True

        def run(self):
            called['run'] = True

    # Replace MusicPlayerApp in the module under test
    monkeypatch.setattr(test_main, 'MusicPlayerApp', FakeApp)

    # Call main and assert it returns 0 and called run
    assert test_main.main() == 0
    assert called.get('run') is True
