# AI_TASK_STATE.md

## Current Branch
`feature/03-fix-missing-features` (branched off `main` @ `35b3928`, known-good baseline: 59 tests, ruff clean)

## Purpose
Close ROADMAP **Missing Features / Gaps** #11, #12, #13 — local-file metadata polling,
robust playlist item resolution, a keyboard binding for `action_play_playlist` — plus an
in-session bug fix: M3U playlists of radio URLs were mislabeled "Local File" and never got
live icy-title metadata.

## Completed This Session

### Gap #11 — local-file metadata polling (#897 lines, `src/pytuiplayer/tui_app.py`)
- `_refresh_metadata` dispatches on a new `_stream_source` flag: streams ->
  `_refresh_stream_metadata` (icy-title/media-title); local file -> `_refresh_local_metadata`
  (mutagen `artist - title`, cached per source).
- New `_refresh_stream_metadata()` (extracted from the old radio block) and `_read_local_tags()`.
- `play_local` records `_current_local_source` on both branches; URL branch now sets
  `_stream_source = True`, filesystem branch sets it False.

### Gap #12 — robust playlist item resolution
- New `_resolve_playlist_items(local_list)`: tries `items`, then `children`, returns a plain
  `list`, never raises. `action_play_playlist` uses it.

### Gap #13 — playlist keyboard binding
- `BINDINGS` gained `Binding("o", "play_playlist", description="Play playlist from start")`.

### Bug fix — M3U radio URL entries must be streams (not "Local File")
- Root cause: `play_local` routed M3U URL entries through its URL branch which set
  `currently_playing = "local"` and labeled the source `"Local File"`; `_refresh_metadata`
  only polled streams when `option_mode == "radio"`, so M3U radio URLs got no metadata.
- Fix: `_stream_source` flag (True for any network stream — live radio OR an M3U URL entry).
  `_refresh_metadata` keys off it; `play_local` URL branch sets it + labels `"Radio"`;
  `action_stop` clears it. Progress-bar title display also keys off `_stream_source`.

### Tests
- `src/tests/test_feature_03_missing_features.py` — 400 lines, **17 tests** (all pass):
  - #11: `test_local_metadata_polling_updates_title`, `_is_cached_per_source`,
    `_falls_back_to_media_title`, `test_radio_metadata_path_still_works` (regression),
    `test_play_local_records_current_source`
  - #12: `test_action_play_playlist_resolves_item`, `_without_items_attribute`,
    `test_resolve_playlist_items_never_raises`, `test_action_play_playlist_reports_empty_playlist`
  - #13: `test_playlist_keyboard_binding_plays`
  - Bug fix: `test_play_local_url_is_flagged_stream`, `test_play_local_url_polls_stream_metadata`,
    `test_play_local_filesystem_is_not_stream`, `test_stop_clears_stream_flag`,
    `test_update_progress_meta_uses_stream_source`
  - Dataset: `test_load_real_radio_m3u_populates`, `test_real_radio_m3u_entries_play_as_streams`
- Updated pre-existing tests to the `_stream_source` contract:
  `test_backlog_coverage.py::test_refresh_metadata_updates_title_for_radio`,
  `test_tui_app.py::test_progressbar_shows_radio_meta_when_streaming`,
  `test_feature_03_missing_features.py::test_radio_metadata_path_still_works`.
- Added `src/tests/assets/radio_stations_hq.m3u` — the user's real 177-station HQ radio list
  (CRLF + ISO-8859, `:` in titles). Pinned via `src/tests/assets/.gitattributes` (`* -text`) so
  git does not normalize CRLF (keeps `load_m3u` parsing reproducible across platforms).
- Two dataset-driven tests in `test_feature_03_missing_features.py` exercise the real list
  end-to-end: `test_load_real_radio_m3u_populates` (all 177 entries load as URLs, CRLF and
  `:` titles handled) and `test_real_radio_m3u_entries_play_as_streams` (selecting an entry
  plays via the `play_local` URL branch → `_stream_source = True`, labeled "Radio").

### Docs / DB sync
- `scripts/update_testsuite_db.py` — file description updated; 5 new bug-fix backlog rows
  (status `done`).
- `ROADMAP.md` — Missing Features table emptied; feature/03 marked DONE; bug-fix section
  documented; expected count 74.

## Tests
- `uv run pytest -q` → **76 passed in ~9.5s** (59 baseline + 17 new)
- `uv run ruff check .` → All checks passed!
- `report_testsuite_db.py` → run #77: collected 76 / passed 76 (no inflation); **34/34 backlog done**
- Demos: `run_tui_app_demo.py` SUCCESS; `run_radio_demo.py` SUCCESS (live stream)

## Remaining
- None. All three gaps + the M3U radio bug are fixed and tested (incl. the real-list dataset).
  Awaiting user decision on commit/merge.

## Architectural Decisions
- Source kind is now a dedicated `_stream_source` boolean (network stream vs local file),
  decoupled from `option_mode`. Rationale: M3U playlists mix URLs and files within the
  *local* mode, so `option_mode` is the wrong discriminator for metadata polling.
- `_refresh_metadata` is the single 1s dispatch point — no new timer added; stream vs local
  logic lives in `_refresh_stream_metadata` / `_refresh_local_metadata`.
- Local tag reads stay cached per source (`_local_meta_source`) — one mutagen read per track.
- `_stream_source` is cleared by `action_stop` and set by both `play_station` and the
  `play_local` URL branch, so every entry point keeps the flag consistent.

## Next Step
Branch is green (tests + ruff + demos + DB). Await the user's go-ahead to commit with the
`WIP:` convention and/or merge `--no-ff` into `main`.
