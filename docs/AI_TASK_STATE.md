# AI_TASK_STATE.md

## Current Branch
`main` (feature/13-audio-visualizer-v2 merged 2026-10-13)

**Note:** staying on `main` for now — the next feature branch
(`feature/14-metadata-display`) will be cut from `main` when work resumes. See
"Next Steps" below for the recorded plan.

## Current State
- 230 tests pass, ruff clean
- Release counter: 1/3 features since v0.2.0 (v0.3.0 due after 2 more merges)
- Next feature: audio visualization / richer metadata display (not yet started)

## Completed

### feature/13-audio-visualizer-v2 — DataTable Migration + Playback Integration (MERGED to main 2026-10-13)
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
- **230 tests pass**, ruff clean (see top of file for the live branch state)

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
Next feature: audio visualization / richer metadata display. Recorded recommendation:

1. **feature/14-metadata-display (start here — cheap, high impact, all data already in
   the SQLite index):** show richer metadata in NowPlaying (album/year/genre/track#) and
   consider an album-grouped view in the DataTable. No audio decode pipeline needed.
2. **Spike: mpv real-time audio pipeline (stretch goal).** The v1 visualizer was abandoned
   because ffmpeg decode latency made it unusable — do NOT repeat that path. Investigate
   whether mpv can expose live audio level data (audio filter output / PCM pipe / built-in
   volume-meter filter) with acceptable latency, for BOTH streams and local files.
   Only build a VU meter / spectrum on top of it if the spike proves latency is fine.
3. If the mpv spike fails: fall back to pre-computed offline waveforms for local files
   (ffmpeg + numpy, cached per track in the metadata DB) — no real-time path for streams.
4. Deferred: more FTS richness — ranking display, search result highlighting.
