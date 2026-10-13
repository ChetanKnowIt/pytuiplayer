# AI_TASK_STATE.md

## Current Branch
`feature/13-audio-visualizer-v2` (active, multiple commits ahead of main)

## Completed This Session

### Architecture Review (complete)
- Read and analyzed all source modules
- Verified baseline: 156 tests pass, ruff clean

### feature/12-ui-polish (MERGED to main)
All 8 planned items implemented + tested (9 new tests)

### feature/13-audio-visualizer-v2 — DataTable Migration + Playback Integration
Migrated from ListView to DataTable with full playback integration.

**New files:**
- `src/pytuiplayer/metadata_index.py` (~460 lines) — MetadataIndex class
- `src/tests/test_metadata_index.py` (~580 lines) — 32 tests
- `src/tests/test_feature_13_fts_search.py` — 19 FTS integration tests
- `src/tests/test_feature_13_perf.py` — Performance benchmarks
- `src/tests/test_feature_13_search_profile.py` — Search profiling tests
- `src/tests/test_data_table_playback.py` — 10 integration tests (NEW)

**Changes:**
- `constants.py` — Added METADATA_DB_PATH (XDG-compliant)
- `tui_app.py` — Added `on_data_table_row_selected` handler; wrapped `play_local` in try/except
- `playlist.py` — Added `add_columns("Track")` guard in both loaders
- `screens.py` — DataTable support, search wrapped in try/except
- `widgets.py` — _khz/_kbps now show real values per track
- `utils.py` — M3U backslash escape handling in resolve_source

**Tests:** 230 passed

## Architectural decisions
- Mutagen for metadata extraction (2ms per file vs 331ms for mpv)
- SQLite for persistent cache (instant re-loads after first scan)
- FTS5 for full-text search (lightning-fast search across 2000+ tracks)
- Schema migration for forward-compatible database upgrades
- mpv independent of the package (confirmed scope decision)
- Release cadence = 3 merged features → MINOR bump + tag
- DataTable instead of ListView for local list (virtual scrolling = instant with 1000+ items)
- Async I/O (asyncio.to_thread) for all file operations to prevent UI lock

## Current State
- **230 tests pass**
- ruff clean
- Branch: `feature/13-audio-visualizer-v2`

## Performance Profile (2000 items)
| Operation | Time |
|-----------|------|
| Bulk cache lookup (get_tracks_bulk) | 10ms |
| FTS search | 0.04–8ms |
| DataTable add_row (NEW) | ~10ms total |
| Full search flow (NEW) | ~10ms |
| Loading message | Skipped if all cached |

## Known Issues (Backlog)
1. **Visualizer not yet implemented** — waveform/spectrum/VU meter rendering (headline feature)
2. **ffmpeg decode pipeline** — needed for local file visualization

## Next Steps (When Resuming)
1. Implement actual audio visualizer (waveform/spectrum/VU meter ASCII art)
2. Build ffmpeg decode pipeline for local files
3. Integrate visualizer into NowPlaying widget
4. More FTS richness — ranking display, search result highlighting
