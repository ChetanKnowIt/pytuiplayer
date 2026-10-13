# feature/13-audio-visualizer-v2: Integration Roadmap

## Goal
Wire `MetadataIndex` into the app so playlist loading is instant with durations.

## Current State
- `src/pytuiplayer/metadata_index.py` — SQLite-backed metadata cache (done, 23 tracks/sec)
- `src/pytuiplayer/playlist.py` — PlaylistLoader (needs integration)
- `src/pytuiplayer/tui_app.py` — App orchestrator (needs cache initialization)

## Integration Points

### Phase 1: Cache Initialization & Persistence
**File:** `src/pytuiplayer/tui_app.py`

- Initialize `MetadataIndex` in `__init__` with path `~/.local/share/pytuiplayer/metadata.db` (XDG-compliant)
- Store index reference as `self.metadata_index`
- Close DB on app exit

### Phase 2: M3U Loading (Instant)
**File:** `src/pytuiplayer/playlist.py` → `load_m3u()`

Current flow:
1. Parse M3U → extract EXTINF durations
2. Create widgets → mount to ListView
3. Spawn workers for missing durations

New flow:
1. Parse M3U → extract EXTINF durations
2. **Batch-insert to cache** (instant, single transaction)
3. Create widgets with **known durations displayed**
4. For items without EXTINF duration: **check cache first**, then spawn worker

### Phase 3: Local File Loading (Cache-Aware)
**File:** `src/pytuiplayer/playlist.py` → `load_local_files()`

Current flow:
1. `os.walk()` → find MP3 files
2. Create widgets with `--:--` placeholder
3. Spawn `fetch_duration` worker per file (slow, blocks UI)

New flow:
1. `os.walk()` → find MP3 files
2. **Query cache for known durations** (instant)
3. Create widgets with **cached durations displayed** (or `--:--` if unknown)
4. Spawn workers **only for uncached files**

### Phase 4: Background Indexing (Progressive Enhancement)
**File:** `src/pytuiplayer/playlist.py` → `fetch_duration()`

Current: Mutagen per file (slow when done serially for 2000 files)

New: After `fetch_duration` completes, **store result in cache**:
```python
# In fetch_duration():
self.app._store_in_cache(source, duration)
```

This way, every played file gets cached naturally over time.

### Phase 5: Cache-First Duration Fetch
**File:** `src/pytuiplayer/playlist.py` → `fetch_duration()`

```python
async def fetch_duration(self, item_data: dict) -> None:
    source = item_data.get("source")
    
    # Check cache first (fast path)
    cached = self.app.metadata_index.get_track(str(source))
    if cached and cached.get("duration"):
        item_data["duration"] = cached["duration"]
        self._update_widget_label(item_data)
        return
    
    # Fall back to mutagen probe
    duration = await self._probe_duration(source)
    if duration:
        item_data["duration"] = duration
        # Store in cache for next time
        self.app.metadata_index.store_track({
            "path": str(source),
            "duration": duration,
            "indexed_at": time.time(),
        })
        self._update_widget_label(item_data)
```

## Implementation Order

### Step 1: Cache init + M3U integration (smallest, testable)
- Add `MetadataIndex` init to `MusicPlayerApp.__init__`
- Modify `load_m3u()` to insert parsed durations into cache
- Test: load M3U, verify durations show immediately

### Step 2: Local file loading uses cache
- Modify `load_local_files()` to query cache before creating widgets
- Spawn workers only for uncached files
- Test: load local directory, verify cached durations show

### Step 3: Duration workers write to cache
- Modify `fetch_duration()` to store results in cache
- Test: play uncached file, reload → duration shows from cache

### Step 4: Persistence + background indexing
- Store DB in XDG data dir
- Add `index_library()` action for manual full reindex
- Test: restart app → cache persists

### Step 5: Handle cache staleness
- Check file mtime vs indexed_at
- Invalidate stale entries
- Re-index on demand

## Files Modified

| File | Change |
|------|--------|
| `tui_app.py` | Add `self.metadata_index = MetadataIndex(db_path)` in `__init__` |
| `playlist.py` → `load_m3u()` | Insert durations to cache, show known durations |
| `playlist.py` → `load_local_files()` | Query cache, spawn workers only for unknown |
| `playlist.py` → `fetch_duration()` | Store result in cache |
| `constants.py` | Add `METADATA_DB_PATH` constant |
| `tests/test_metadata_index.py` | Unit tests for MetadataIndex class |
| `tests/test_tui_app.py` | Integration tests for cache-aware loading |

## Testing Strategy

### Unit Tests (`test_metadata_index.py`)
- `test_index_creates_schema` — DB initializes correctly
- `test_index_single_file` — Mutagen probes one file
- `test_index_batch_insert` — Batch insert is faster than individual
- `test_index_skip_existing` — Re-scan skips already-indexed files
- `test_index_get_all_tracks` — Query returns all tracks
- `test_index_get_track` — Query single track by path
- `test_index_persistence` — Data survives close/reopen

### Integration Tests (`test_tui_app.py`)
- `test_load_m3u_uses_cache` — M3U durations stored and retrieved
- `test_load_local_uses_cache` — Local files query cache first
- `test_fetch_duration_writes_cache` — Playing file caches duration
- `test_cache_persists_across_sessions` — DB survives app restart

## Success Criteria

- [ ] M3U with 2000 entries loads in < 2 seconds (durations from EXTINF + cache)
- [ ] Local directory with 2000 files: first scan ~1.5 min, subsequent loads instant
- [ ] Durations show immediately (no "--:--" placeholder for cached files)
- [ ] Cache persists across app restarts
- [ ] No "durations loading..." message spam
- [ ] All 156 existing tests still pass
- [ ] ruff check clean
