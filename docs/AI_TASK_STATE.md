# AI_TASK_STATE.md

## Current Branch
`feature/10-playlist-export` — **Feature #6 (playlist export) implemented & green**, not yet merged
to `main`. 147 tests pass, ruff clean, 98/98 backlog done. (Features #3 and #4 were merged to `main`
earlier this session: `feature/08` → commit `03cadc5`; `feature/09` → commit `4a2903d`, both pushed.)

## Completed This Session (3-feature batch: #3 history → #4 shuffle/repeat → #6 export)

### SKILL.md stale-architecture fix
`~/.hermes/skills/textual-music-player/SKILL.md` corrected (it described the pre-feature/05
monolith). AGENTS.md + live code remain authoritative.

### feature/08-playback-history — Feature #3 (MERGED to main, pushed)
`HistoryTracker` controller + `H` replay binding + 15 tests. Merged `--no-ff` (`03cadc5`).

### feature/09-shuffle-repeat — Feature #4 (MERGED to main, pushed)
Shuffle/repeat modes: `PlaylistNavigator._next_index` + `z`/`r` bindings + `NowPlaying` reactives
+ 20 tests. Merged `--no-ff` (`4a2903d`).

### feature/10-playlist-export — Feature #6 (ROADMAP Low Priority #6)
Exports the current local playlist to an EXTINF M3U file. Pure file I/O.

**New / changed files:**
- `src/pytuiplayer/exporter.py` (new, ~75 lines) — `PlaylistExporter` with `build_lines(items)`
  (emits `#EXTM3U` + `#EXTINF:<secs or -1>,<title>` + `<source>`), `export_m3u(path, items)`,
  `default_export_path()`. `@profile` on each method.
- `src/pytuiplayer/tui_app.py` — `self.playlist_exporter = PlaylistExporter(self)` in `__init__`;
  binding `e` → `action_export_playlist()` (exports to `~/Music/pytuiplayer/playlist.m3u`, warns
  when empty); `export_playlist_to(path)` thin accessor.
- `src/tests/test_feature_10_playlist_export.py` (new, 10 tests) — `build_lines` format (EXTM3U/
  EXTINF, unknown-duration→-1, missing-source skip, filename fallback), `export_m3u` file writing
  + parent-dir creation + empty-header, and app-level `export_playlist_to` / `action_export_playlist`.
- `scripts/update_testsuite_db.py` — `FILE_DESCRIPTIONS` + 10 BACKLOG rows (Low Priority #6).
- `ROADMAP.md` — added `feature/10-playlist-export` section; removed #6 from unscheduled list.

**Verification:**
- `uv run pytest -q` → **147 passed** (137 prior + 10 new), 2 benign `DirectoryTree.watch_path`
  coroutine warnings.
- `uv run ruff check .` → **All checks passed!**
- `uv run python scripts/update_testsuite_db.py` → 98 backlog rows synced (98/98 done).
- `testsuite.db` report: 98/98 backlog items marked done.

**Not yet committed/merged** (user did not ask; branch `feature/10-playlist-export` is local).

## Decision: Next 3 Features (user-confirmed) — COMPLETE
Order: #3 history → #4 shuffle/repeat → #6 export. All three implemented; #3 and #4 merged+pushed;
#6 remains on its branch pending merge. Remaining ROADMAP Low Priority items: #2 favorites,
#5 configurable keys, #7 visualizer.

## Next Step
Merge `feature/10-playlist-export` to `main` (--no-ff) and push, then re-verify gates on main.
After that, the 3-feature batch is fully landed and main is the known-good baseline. Optionally
update AGENTS.md / SKILL.md "Low Priority" lists to reflect #3/#4/#6 closure (ROADMAP already
reflects it). No further features are in scope unless the user requests more (e.g. #2/#5/#7).
