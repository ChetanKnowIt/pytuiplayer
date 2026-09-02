# AI_TASK_STATE.md

## Current Branch
`feature/13-audio-visualizer-v2` (paused, 8 commits ahead of main)

## Completed This Session

### Architecture Review (complete)
- Read and analyzed all source modules
- Verified baseline: 156 tests pass, ruff clean

### feature/12-ui-polish (MERGED to main)
All 8 planned items implemented + tested (9 new tests)

### feature/13-audio-visualizer-v2 — Metadata Cache + FTS Search (PAUSED)
SQLite-backed metadata cache with FTS5 full-text search for instant playlist loading.

**New files:**
- `src/pytuiplayer/metadata_index.py` (~460 lines) — MetadataIndex class
- `src/tests/test_metadata_index.py` (~580 lines) — 32 tests

**Changes:**
- `constants.py` — Added METADATA_DB_PATH (XDG-compliant)
- `tui_app.py` — Initialize MetadataIndex in __init__, close on cleanup, update NowPlaying with real metadata
- `playlist.py` — load_m3u() and load_local_files() are cache-aware, fetch_duration() writes to cache
- `widgets.py` — _khz/_kbps now show real values per track
- `scripts/update_testsuite_db.py` — Registered new test file + backlog items

**Tests:** 32 new tests, all passing (188 total: 156 baseline + 32 new)

## Architectural decisions
- Mutagen for metadata extraction (2ms per file vs 331ms for mpv)
- SQLite for persistent cache (instant re-loads after first scan)
- FTS5 for full-text search (lightning-fast search across 2000+ tracks)
- Schema migration for forward-compatible database upgrades
- mpv independent of the package (confirmed scope decision)
- Release cadence = 3 merged features → MINOR bump + tag

## Current State
- **188 tests pass** (156 baseline + 32 new)
- ruff clean
- Branch: `feature/13-audio-visualizer-v2` (8 commits)

## Known Issues (Backlog)
1. **M3U first-load slow** — files without `#EXTINF` have unknown durations initially
2. **Search widget janky** — UI locks on each keystroke, needs debouncing + async search
3. **No FTS integration tests** — search widget not yet wired to FTS

## Next Steps (When Resuming)
1. Add tests for FTS search integration
2. Fix search widget (debounce + async FTS query)
3. Optimize M3U first-load (parallel probing)
4. Wire FTS search into LocalScreen search widget

Remaining ROADMAP Low Priority items:
- **Later:** #5 configurable keybindings, #2 station favorites
