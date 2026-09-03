# AI_TASK_STATE.md

## Current Branch
`feature/13-audio-visualizer-v2` (active, multiple commits ahead of main)

## Completed This Session

### Architecture Review (complete)
- Read and analyzed all source modules
- Verified baseline: 156 tests pass, ruff clean

### feature/12-ui-polish (MERGED to main)
All 8 planned items implemented + tested (9 new tests)

### feature/13-audio-visualizer-v2 — Metadata Cache + FTS Search + DataTable (ACTIVE)
SQLite-backed metadata cache with FTS5 full-text search and DataTable virtual scrolling for instant playlist loading.

**New files:**
- `src/pytuiplayer/metadata_index.py` (~460 lines) — MetadataIndex class
- `src/tests/test_metadata_index.py` (~580 lines) — 32 tests
- `src/tests/test_feature_13_fts_search.py` — 19 FTS integration tests
- `src/tests/test_feature_13_perf.py` — Performance benchmarks
- `src/tests/test_feature_13_search_profile.py` — Search profiling tests

**Changes:**
- `constants.py` — Added METADATA_DB_PATH (XDG-compliant)
- `tui_app.py` — Initialize MetadataIndex in __init__, close on cleanup, update NowPlaying with real metadata, DataTable support
- `playlist.py` — load_m3u() and load_local_files() are cache-aware with bulk lookup, fetch_duration() writes to cache, DataTable support
- `widgets.py` — _khz/_kbps now show real values per track
- `screens.py` — LocalScreen uses DataTable (virtual scrolling), debounced search with query cache, M3U missing file handling
- `utils.py` — M3U backslash escape handling in resolve_source
- `scripts/update_testsuite_db.py` — Registered new test files + backlog items

**Tests:** 217 passed (3 remaining failures in test infrastructure need FakeList.add_row updates)

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
- **217 tests pass**
- ruff clean
- Branch: `feature/13-audio-visualizer-v2`

## Performance Profile (2000 items)
| Operation | Time |
|-----------|------|
| Bulk cache lookup (get_tracks_bulk) | 10ms |
| FTS search | 0.04–8ms |
| Widget creation (ListView, OLD) | ~94ms per 1000 items |
| DataTable add_row (NEW) | ~10ms total |
| Full search flow (NEW) | ~10ms |
| Loading message | Skipped if all cached |

## Known Issues (Backlog)
1. **3 test failures** — FakeList classes in test_feature_02_design_flows.py and test_feature_03_missing_features.py need add_row method
2. **Visualizer not yet implemented** — waveform/spectrum/VU meter rendering (headline feature)
3. **ffmpeg decode pipeline** — needed for local file visualization

## Next Steps (When Resuming)
1. Fix remaining 3 test failures (add add_row to FakeList classes)
2. Implement actual audio visualizer (waveform/spectrum/VU meter ASCII art)
3. Build ffmpeg decode pipeline for local files
4. Integrate visualizer into NowPlaying widget
5. More FTS richness — ranking display, search result highlighting
