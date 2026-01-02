from pytuiplayer.tui_app import NowPlaying, NowPlayingMessage


def test_now_playing_message_updates_widget():
    nw = NowPlaying()
    # initial defaults
    assert nw.title == "Nothing playing"
    assert nw.state == "⏹"

    # deliver a message and assert widget updates its fields
    msg = NowPlayingMessage(sender=None, title="Artist X - Track Y", source="Local File", state="▶")
    nw.on_now_playing_message(msg)

    assert nw.title == "Artist X - Track Y"
    assert nw.source == "Local File"
    assert nw.state == "▶"

    rendered = nw.render()
    assert "Artist X - Track Y" in rendered


def test_now_playing_marquee_rotates_and_has_fixed_width():
    nw = NowPlaying()
    nw.title = "ThisIsAVeryLongSongTitleThatShouldScroll"

    # wide marquee; expect returned slice to have requested width
    s1 = nw._marquee(12)
    # advance offset and ensure visible change (rotation)
    nw._tick()
    s2 = nw._marquee(12)

    assert len(s1) == 12
    assert len(s2) == 12
    assert s1 != s2
