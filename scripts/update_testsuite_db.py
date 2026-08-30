#!/usr/bin/env python3
"""Rebuild / enrich the pytuiplayer test inventory in ``testsuite.db``.

This is the *manual* companion to the automatic ``conftest.py`` hook (which
writes the ``tests`` + ``runs`` tables on every pytest run). This script:

1. Ensures ``files`` rows exist and refreshes their ``line_count`` / ``description``.
2. Mirrors the ROADMAP Test Backlog into the ``backlog`` table so the dashboard
   can show open vs. closed items. The *status* column is the source of truth for
   "done/pending" and is preserved across runs (never auto-flipped to pending).
3. Leaves the ``tests`` (per-function) and ``runs`` tables to the pytest hook.

Usage:
    uv run python scripts/update_testsuite_db.py
    uv run python scripts/update_testsuite_db.py --db /path/to/testsuite.db
    uv run python scripts/update_testsuite_db.py --reset-backlog   # recreate backlog rows

It is safe to re-run: all writes use upsert semantics.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as a standalone script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src" / "tests"))

from testsuite_db import (  # noqa: E402
    REPO_ROOT,
    connect,
    discover_tests,
    upsert_backlog,
    upsert_file,
)

# ---------------------------------------------------------------------------
# Module descriptions (kept here so the DB carries human context without
# bloating ROADMAP.md). Edit freely; these are upserted, not destructive.
# ---------------------------------------------------------------------------
FILE_DESCRIPTIONS = {
    "src/tests/test_main_entry.py": "Console-script entry point smoke test.",
    "src/tests/test_app_integration.py": "End-to-end playlist play + progress flow.",
    "src/tests/test_station_player.py": "StationPlayer URL forwarding + JSON reload.",
    "src/tests/test_now_playing_widget.py": "NowPlaying message handling + marquee.",
    "src/tests/test_mpv_player.py": "MPVPlayer wrapper play/pause/seek/volume.",
    "src/tests/test_tui_app.py": "App actions, loaders, visibility, regressions.",
    "src/tests/test_radio_integration.py": "Live radio stream (network, auto-skips offline).",
    "src/tests/test_backlog_coverage.py": "ROADMAP Test Backlog coverage suite.",
    "src/tests/test_feature_02_design_flows.py": "feature/02 acceptance tests (design flows).",
    "src/tests/test_feature_03_missing_features.py":
        "feature/03: local metadata, playlist action+binding, M3U radio fix, real-list dataset.",
    "src/tests/test_feature_04_medium_priority.py":
        "feature/04 acceptance tests (recursive local-file scanning).",
    "src/tests/test_feature_05_playlist_search.py":
        "feature/05: playlist search/filter + Winamp UI overhaul.",
    "src/tests/test_feature_08_playback_history.py":
        "feature/08: playback history tracker (record/recent/replay), H binding.",
    "src/tests/test_feature_09_shuffle_repeat.py":
        "feature/09: shuffle/repeat modes (navigator index logic + z/r bindings).",
}

# ---------------------------------------------------------------------------
# ROADMAP Test Backlog mirror. `status` is the human-maintained source of
# truth; it is preserved on re-runs unless --reset-backlog is given.
# ---------------------------------------------------------------------------
BACKLOG = [
    # Missing Unit Tests
    ("test_on_button_pressed_play_pause_stop", "unit",
     "Button handlers call mpv correctly", "done", "ROADMAP Test Backlog #2"),
    ("test_on_list_view_selected_station_mode", "unit",
     "Station selection triggers play_station", "done", "ROADMAP Test Backlog #3"),
    ("test_on_list_view_selected_local_mode", "unit",
     "Local selection triggers play_local", "done", "ROADMAP Test Backlog #4"),
    ("test_action_seek_forward_backward", "unit",
     "Seek calls mpv.seek with correct delta", "done", "ROADMAP Test Backlog #5"),
    ("test_action_seek_to_percent_no_absolute_fallback", "unit",
     "Relative fallback works", "done", "ROADMAP Test Backlog #6"),
    ("test_update_progress_sets_bar_values", "unit",
     "Progress/duration set on bar", "done", "ROADMAP Test Backlog #7"),
    ("test_refresh_metadata_updates_title_for_radio", "unit",
     "ICY title updates current_title", "done", "ROADMAP Test Backlog #8"),
    ("test_refresh_metadata_noop_for_local_mode", "unit",
     "No metadata polling in local mode", "done", "ROADMAP Test Backlog #9"),
    ("test_play_local_url_bypasses_file_checks", "unit",
     "URL handling path", "done", "ROADMAP Test Backlog #10"),
    ("test_play_local_failure_shows_error", "unit",
     "Error toast on play failure", "done", "ROADMAP Test Backlog #11"),
    ("test_load_m3u_respects_max_playlist_items", "unit",
     "Truncation honored", "done", "ROADMAP Test Backlog #12"),
    ("test_load_m3u_handles_aiofiles_and_sync_fallback", "unit",
     "Both code paths", "done", "ROADMAP Test Backlog #13"),
    ("test_directory_tree_json_in_radio_mode", "unit",
     "Station file loading", "done", "ROADMAP Test Backlog #14"),
    ("test_directory_tree_unsupported_file_shows_error", "unit",
     "Error notification", "done", "ROADMAP Test Backlog #15"),
    ("test_volume_up_clamps_at_100", "unit",
     "Volume ceiling", "done", "ROADMAP Test Backlog #16"),
    ("test_volume_down_clamps_at_0_and_mutes", "unit",
     "Mute on zero", "done", "ROADMAP Test Backlog #17"),
    ("test_mute_restores_previous_volume", "unit",
     "_prev_volume logic", "done", "ROADMAP Test Backlog #18"),
    ("test_now_playing_marquee_scrolls_long_titles", "unit",
     "Marquee offset logic", "done", "ROADMAP Test Backlog #19"),
    ("test_progressbar_render_with_meta_no_duration", "unit",
     "Radio metadata display", "done", "ROADMAP Test Backlog #20"),
    ("test_fetch_duration_updates_item_data", "unit",
     "Duration stored in item.data", "done", "ROADMAP Test Backlog #1"),
    # Integration / Widget Tests
    ("test_now_playing_widget_renders_countdown", "integration",
     "Remaining time display", "done", "ROADMAP Integration #1"),
    ("test_volume_indicator_shows_muted_state", "integration",
     "Mute icon", "done", "ROADMAP Integration #2"),
    ("test_mode_switch_stops_playback", "integration",
     "mpv.stop() on mode change", "done", "ROADMAP Integration #3"),
    ("test_mode_switch_updates_visibility", "integration",
     "All three widgets toggled", "done", "ROADMAP Integration #4"),
    # feature/03 — Missing Features / Gaps #11, #12, #13
    ("test_local_metadata_polling_updates_title", "unit",
     "_refresh_metadata reads mutagen tags for local files", "done",
     "ROADMAP Gap #11"),
    ("test_action_play_playlist_resolves_item", "unit",
     "action_play_playlist resolves item.data without ListView.items", "done",
     "ROADMAP Gap #12"),
    ("test_playlist_keyboard_binding_plays", "unit",
     "'o' binding triggers action_play_playlist and plays first item", "done",
     "ROADMAP Gap #13"),
    # feature/03 — bug fix: M3U radio URL entries treated as streams (not "Local File")
    ("test_play_local_url_is_flagged_stream", "unit",
     "URL source (M3U radio) plays as stream, labeled Radio", "done",
     "M3U radio bug"),
    ("test_play_local_url_polls_stream_metadata", "unit",
     "M3U radio URL gets icy-title polling", "done",
     "M3U radio bug"),
    ("test_play_local_filesystem_is_not_stream", "unit",
     "Local .mp3 path is not a stream", "done",
     "M3U radio bug"),
    ("test_stop_clears_stream_flag", "unit",
     "stop clears currently_playing + _stream_source", "done",
     "M3U radio bug"),
    ("test_update_progress_meta_uses_stream_source", "unit",
     "progress bar shows stream title for M3U radio URLs", "done",
     "M3U radio bug"),
    # feature/03 — dataset-driven coverage with the real HQ radio list
    # (src/tests/assets/radio_stations_hq.m3u)
    ("test_load_real_radio_m3u_populates", "integration",
     "Real 177-station M3U (CRLF + ':' titles) loads; all entries are URLs", "done",
     "M3U radio bug"),
    ("test_real_radio_m3u_entries_play_as_streams", "integration",
     "Selecting a real list entry plays as a stream labeled Radio", "done",
     "M3U radio bug"),
    # feature/04 — Medium Priority #1: recursive directory scanning
    ("test_load_local_files_recursive", "unit",
     "load_local_files walks subdirectories; nested .mp3s appear", "done",
     "Medium #1"),
    ("test_load_local_files_recursive_respects_max_playlist_items", "unit",
     "nested tree capped at max_playlist_items", "done",
     "Medium #1"),
    ("test_load_local_files_recursive_batched_mounting", "unit",
     "items mounted in playlist_batch_size batches", "done",
     "Medium #1"),
    ("test_load_local_files_top_level_still_works", "unit",
     "flat directory still behaves as before", "done",
     "Medium #1"),
    ("test_switch_to_local_does_not_crash_on_fetch_duration_worker", "unit",
     "Radio->Local switch does not crash fetch_duration worker", "done",
     "Medium #1"),
    # feature/05 — Low Priority #1: playlist search/filter
    ("test_search_filters_items_by_title_substring", "unit",
     "Search input filters local list by title substring", "done",
     "Low Priority #1"),
    ("test_search_is_case_insensitive", "unit",
     "Search is case-insensitive", "done",
     "Low Priority #1"),
    ("test_clearing_search_restores_full_list", "unit",
     "Clearing search restores the full list", "done",
     "Low Priority #1"),
    ("test_search_no_matches_shows_empty_list", "unit",
     "Search with no matches shows empty list", "done",
     "Low Priority #1"),
    ("test_search_special_chars_dont_break_filtering", "unit",
     "Special regex chars in search don't break filtering", "done",
     "Low Priority #1"),
    # feature/05 — Winamp UI overhaul
    ("test_now_playing_winamp_led_display", "unit",
     "NowPlaying renders Winamp-style LED display", "done",
     "Winamp UI"),
    ("test_now_playing_winamp_no_position", "unit",
     "NowPlaying shows '--' when no position info", "done",
     "Winamp UI"),
    ("test_progress_bar_winamp_seek_bar", "unit",
     "ProgressBar renders Winamp-style seek bar", "done",
     "Winamp UI"),
    ("test_progress_bar_winamp_unknown_duration", "unit",
     "ProgressBar shows metadata when duration is unknown", "done",
     "Winamp UI"),
    ("test_volume_indicator_winamp_bar", "unit",
     "VolumeIndicator renders Winamp-style volume bar", "done",
     "Winamp UI"),
    ("test_volume_indicator_winamp_muted", "unit",
     "VolumeIndicator shows MUTE when muted", "done",
     "Winamp UI"),
    ("test_local_screen_compose_mode_content_has_search_input", "unit",
     "LocalScreen composes a search input widget", "done",
     "Low Priority #1"),
    ("test_local_screen_compose_mode_content_has_loading_status", "unit",
     "LocalScreen composes a loading status widget", "done",
     "Low Priority #1"),
    ("test_mode_screen_class_has_prev_next_button_ids", "unit",
     "ModeScreen defines prev/next button IDs", "done",
     "Winamp UI"),
    # feature/08 — Low Priority #3: playback history
    ("test_history_record_and_recent_order", "unit",
     "HistoryTracker records entries most-recent-first", "done",
     "Low Priority #3"),
    ("test_history_dedupes_consecutive_repeats", "unit",
     "Consecutive duplicate plays are deduped", "done",
     "Low Priority #3"),
    ("test_history_is_not_deduped_across_non_consecutive", "unit",
     "Re-play after a different item is kept", "done",
     "Low Priority #3"),
    ("test_history_recent_limits_to_n", "unit",
     "recent(n) returns at most n entries", "done",
     "Low Priority #3"),
    ("test_history_caps_at_max_items", "unit",
     "Bounded deque caps at max_items", "done",
     "Low Priority #3"),
    ("test_history_ignores_empty_title_or_source", "unit",
     "Empty title/source are not recorded", "done",
     "Low Priority #3"),
    ("test_history_replay_returns_entry_or_none", "unit",
     "replay(index) returns entry or None", "done",
     "Low Priority #3"),
    ("test_history_clear", "unit",
     "clear() empties history", "done",
     "Low Priority #3"),
    ("test_play_station_records_history", "unit",
     "play_station records a radio entry", "done",
     "Low Priority #3"),
    ("test_play_local_filesystem_records_history", "unit",
     "play_local (file) records a local entry", "done",
     "Low Priority #3"),
    ("test_play_local_url_records_history_as_local_mode", "unit",
     "play_local (URL) records as local mode", "done",
     "Low Priority #3"),
    ("test_history_interleaved_radio_and_local", "unit",
     "Interleaved radio/local produce correct order", "done",
     "Low Priority #3"),
    ("test_action_play_history_last_replays_local", "unit",
     "'H' binding replays the last local item", "done",
     "Low Priority #3"),
    ("test_action_play_history_last_no_history_shows_warning", "unit",
     "Replay with empty history shows warning", "done",
     "Low Priority #3"),
    ("test_history_tracker_instantiated_on_app", "unit",
     "App instantiates a HistoryTracker", "done",
     "Low Priority #3"),
    # feature/09 — Low Priority #4: shuffle/repeat modes
    ("test_next_index_sequential_off_moves_forward", "unit",
     "Sequential next advances index", "done",
     "Low Priority #4"),
    ("test_next_index_sequential_off_stops_at_end", "unit",
     "Sequential 'off' stops at last item", "done",
     "Low Priority #4"),
    ("test_next_index_sequential_off_stops_at_start", "unit",
     "Sequential 'off' stops at first item", "done",
     "Low Priority #4"),
    ("test_next_index_repeat_all_wraps_forward_and_back", "unit",
     "Repeat 'all' wraps at both ends", "done",
     "Low Priority #4"),
    ("test_next_index_repeat_one_replays_current", "unit",
     "Repeat 'one' replays current item", "done",
     "Low Priority #4"),
    ("test_next_index_shuffle_picks_different_item", "unit",
     "Shuffle picks a different item", "done",
     "Low Priority #4"),
    ("test_next_index_shuffle_never_equals_current", "unit",
     "Shuffle never returns the current index", "done",
     "Low Priority #4"),
    ("test_next_index_shuffle_single_item_stays", "unit",
     "Shuffle with one item stays put", "done",
     "Low Priority #4"),
    ("test_next_index_none_current_defaults_to_zero_then_advances", "unit",
     "No selection defaults to first item", "done",
     "Low Priority #4"),
    ("test_next_index_empty_list_is_none", "unit",
     "Empty list yields no navigation", "done",
     "Low Priority #4"),
    ("test_toggle_shuffle_flips_state", "unit",
     "'z' toggles shuffle on/off", "done",
     "Low Priority #4"),
    ("test_cycle_repeat_rotates_off_one_all", "unit",
     "'r' cycles off->one->all->off", "done",
     "Low Priority #4"),
    ("test_toggle_shuffle_updates_nowplaying_indicator", "unit",
     "Shuffle toggle updates NowPlaying reactive", "done",
     "Low Priority #4"),
    ("test_play_next_repeat_one_replays_same_local_index", "unit",
     "play_next with repeat=one replays local index", "done",
     "Low Priority #4"),
    ("test_play_next_repeat_all_wraps_local", "unit",
     "play_next with repeat=all wraps local list", "done",
     "Low Priority #4"),
    ("test_play_next_sequential_off_stops_at_end_local", "unit",
     "play_next sequential stops at local list end", "done",
     "Low Priority #4"),
    ("test_play_next_shuffle_picks_different_local", "unit",
     "play_next shuffle picks different local item", "done",
     "Low Priority #4"),
    ("test_play_previous_sequential_off_stops_at_start_radio", "unit",
     "play_previous sequential stops at radio start", "done",
     "Low Priority #4"),
    ("test_play_next_radio_repeat_all_wraps", "unit",
     "play_next radio repeat=all wraps", "done",
     "Low Priority #4"),
    ("test_navigator_instantiated_on_app", "unit",
     "App instantiates a PlaylistNavigator", "done",
     "Low Priority #4"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(REPO_ROOT / "testsuite.db"), help="DB path")
    parser.add_argument(
        "--reset-backlog",
        action="store_true",
        help="Recreate backlog rows from the built-in list (preserves status otherwise).",
    )
    args = parser.parse_args(argv)

    db_path = Path(args.db)
    conn = connect(db_path)
    try:
        # 1) Refresh file rows (line counts + descriptions).
        discovered = discover_tests()
        for d in discovered:
            desc = FILE_DESCRIPTIONS.get(d["file"], "")
            upsert_file(conn, d["file"], desc, d["line_count"])
        print(f"[update] refreshed {len(discovered)} test module file rows")

        # 2) Sync backlog mirror.
        if args.reset_backlog:
            conn.execute("DELETE FROM backlog")
        for name, kind, desc, status, source in BACKLOG:
            upsert_backlog(conn, name, kind, desc, status, source)
        print(f"[update] synced {len(BACKLOG)} backlog rows (status preserved)")

        conn.commit()
    finally:
        conn.close()

    print(f"[update] done -> {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
