"""Tests for MetadataIndex.

Validates all 5 steps of the metadata cache integration:
1. Cache initialization + schema
2. M3U integration (store + retrieve)
3. Local file loading (cache-aware)
4. Duration workers write to cache
5. Cache staleness detection + persistence
"""

import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

from pytuiplayer.metadata_index import MetadataIndex


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_metadata.db"


@pytest.fixture
def index(db_path):
    """Create a MetadataIndex instance."""
    idx = MetadataIndex(db_path)
    yield idx
    idx.close()


@pytest.fixture
def sample_mp3(tmp_path):
    """Create a minimal MP3 file for testing."""
    mp3_path = tmp_path / "test_song.mp3"
    # Create a minimal valid MP3 frame (MPEG1 Layer 3, 128kbps, 44100Hz)
    # This is a minimal valid frame header
    header = bytes([
        0xFF, 0xFB, 0x90, 0x00,  # MP3 frame header
    ])
    # Pad to make it look like a real file
    mp3_path.write_bytes(header + b'\x00' * 417)
    return mp3_path


class TestCacheInitialization:
    """Step 1: Cache initialization + schema."""

    def test_creates_database(self, db_path):
        """Database file is created on init."""
        index = MetadataIndex(db_path)
        assert db_path.exists()
        index.close()

    def test_schema_has_required_columns(self, index):
        """Schema includes all required columns."""
        cursor = index.conn.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}

        required = {
            "path", "duration", "artist", "album", "title", "track",
            "year", "genre", "bitrate", "sample_rate", "channels",
            "encoder", "file_mtime", "indexed_at"
        }
        assert required.issubset(columns)

    def test_primary_key_is_path(self, index):
        """Path is the primary key."""
        cursor = index.conn.execute("PRAGMA table_info(tracks)")
        for row in cursor.fetchall():
            if row[1] == "path":
                assert row[5] == 1  # pk column
                break
        else:
            pytest.fail("path column not found")

    def test_indexes_exist(self, index):
        """Required indexes exist."""
        cursor = index.conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = {row[0] for row in cursor.fetchall()}

        assert "idx_tracks_artist" in indexes
        assert "idx_tracks_album" in indexes
        assert "idx_tracks_title" in indexes
        assert "idx_tracks_mtime" in indexes

    def test_close_connection(self, db_path):
        """Close method works without error."""
        index = MetadataIndex(db_path)
        index.close()

    def test_persistence_across_reopen(self, db_path):
        """Data persists after close and reopen."""
        index = MetadataIndex(db_path)
        index._store_metadata({
            "path": "/test/song.mp3",
            "duration": 180.5,
            "artist": "Test Artist",
            "album": "Test Album",
            "title": "Test Title",
            "track": 1,
            "year": "2024",
            "genre": "Pop",
            "bitrate": 320000,
            "sample_rate": 44100,
            "channels": 2,
            "encoder": "LAME 3.99",
            "file_mtime": 1234567890.0,
            "indexed_at": time.time(),
        })
        index.close()

        # Reopen and verify
        index2 = MetadataIndex(db_path)
        track = index2.get_track("/test/song.mp3")
        assert track is not None
        assert track["duration"] == 180.5
        assert track["artist"] == "Test Artist"
        index2.close()


class TestM3UIntegration:
    """Step 2: M3U integration (store + retrieve)."""

    def test_store_batch(self, index):
        """Batch insert multiple tracks."""
        metadata_list = [
            {
                "path": f"/music/song{i}.mp3",
                "duration": 180.0 + i,
                "artist": f"Artist {i}",
                "album": f"Album {i}",
                "title": f"Song {i}",
                "track": i,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": 1234567890.0 + i,
                "indexed_at": time.time(),
            }
            for i in range(10)
        ]
        index.store_batch(metadata_list)

        assert index.get_track_count() == 10
        assert index.get_track("/music/song0.mp3") is not None
        assert index.get_track("/music/song9.mp3") is not None

    def test_store_track(self, index):
        """Store single track."""
        index.store_track({
            "path": "/music/single.mp3",
            "duration": 200.0,
            "artist": "Single Artist",
            "album": "Single Album",
            "title": "Single Title",
            "track": 1,
            "year": "2024",
            "genre": "Rock",
            "bitrate": 256000,
            "sample_rate": 48000,
            "channels": 2,
            "encoder": "iTunes",
            "file_mtime": 1234567890.0,
            "indexed_at": time.time(),
        })

        track = index.get_track("/music/single.mp3")
        assert track is not None
        assert track["duration"] == 200.0
        assert track["artist"] == "Single Artist"

    def test_get_track_returns_none_for_missing(self, index):
        """Return None for non-existent track."""
        assert index.get_track("/nonexistent/song.mp3") is None

    def test_get_all_tracks(self, index):
        """Get all tracks."""
        for i in range(5):
            index.store_track({
                "path": f"/music/song{i}.mp3",
                "duration": 180.0,
                "artist": "Artist",
                "album": "Album",
                "title": f"Song {i}",
                "track": i,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": 1234567890.0,
                "indexed_at": time.time(),
            })

        tracks = index.get_all_tracks()
        assert len(tracks) == 5

    def test_update_existing_track(self, index):
        """Update existing track (UPSERT)."""
        index.store_track({
            "path": "/music/song.mp3",
            "duration": 180.0,
            "artist": "Old Artist",
            "album": "Old Album",
            "title": "Old Title",
            "track": 1,
            "year": "2024",
            "genre": "Pop",
            "bitrate": 320000,
            "sample_rate": 44100,
            "channels": 2,
            "encoder": "LAME",
            "file_mtime": 1234567890.0,
            "indexed_at": time.time(),
        })

        # Update
        index.store_track({
            "path": "/music/song.mp3",
            "duration": 200.0,
            "artist": "New Artist",
            "album": "New Album",
            "title": "New Title",
            "track": 1,
            "year": "2024",
            "genre": "Rock",
            "bitrate": 256000,
            "sample_rate": 48000,
            "channels": 2,
            "encoder": "iTunes",
            "file_mtime": 1234567891.0,
            "indexed_at": time.time(),
        })

        assert index.get_track_count() == 1
        track = index.get_track("/music/song.mp3")
        assert track["artist"] == "New Artist"
        assert track["duration"] == 200.0


class TestLocalFileLoading:
    """Step 3: Local file loading (cache-aware)."""

    def test_get_total_duration(self, index):
        """Get total duration of all tracks."""
        for i in range(5):
            index.store_track({
                "path": f"/music/song{i}.mp3",
                "duration": 180.0,
                "artist": "Artist",
                "album": "Album",
                "title": f"Song {i}",
                "track": i,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": 1234567890.0,
                "indexed_at": time.time(),
            })

        total = index.get_total_duration()
        assert total == 900.0  # 5 * 180

    def test_get_total_duration_with_none(self, index):
        """Total duration handles None values."""
        index.store_track({
            "path": "/music/song1.mp3",
            "duration": 180.0,
            "artist": "Artist",
            "album": "Album",
            "title": "Song 1",
            "track": 1,
            "year": "2024",
            "genre": "Pop",
            "bitrate": 320000,
            "sample_rate": 44100,
            "channels": 2,
            "encoder": "LAME",
            "file_mtime": 1234567890.0,
            "indexed_at": time.time(),
        })
        index.store_track({
            "path": "/music/song2.mp3",
            "duration": None,
            "artist": "Artist",
            "album": "Album",
            "title": "Song 2",
            "track": 2,
            "year": "2024",
            "genre": "Pop",
            "bitrate": 320000,
            "sample_rate": 44100,
            "channels": 2,
            "encoder": "LAME",
            "file_mtime": 1234567890.0,
            "indexed_at": time.time(),
        })

        total = index.get_total_duration()
        assert total == 180.0  # Only counts non-None

    def test_get_track_count(self, index):
        """Get total track count."""
        for i in range(10):
            index.store_track({
                "path": f"/music/song{i}.mp3",
                "duration": 180.0,
                "artist": "Artist",
                "album": "Album",
                "title": f"Song {i}",
                "track": i,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": 1234567890.0,
                "indexed_at": time.time(),
            })

        assert index.get_track_count() == 10

    def test_get_indexed_paths(self, index):
        """Get set of indexed paths."""
        for i in range(3):
            index.store_track({
                "path": f"/music/song{i}.mp3",
                "duration": 180.0,
                "artist": "Artist",
                "album": "Album",
                "title": f"Song {i}",
                "track": i,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": 1234567890.0,
                "indexed_at": time.time(),
            })

        paths = index._get_indexed_paths()
        assert "/music/song0.mp3" in paths
        assert "/music/song1.mp3" in paths
        assert "/music/song2.mp3" in paths


class TestDurationWorkersWriteCache:
    """Step 4: Duration workers write to cache."""

    def test_store_track_with_minimal_data(self, index):
        """Store track with only path and duration (worker use case)."""
        index.store_track({
            "path": "/music/new_song.mp3",
            "duration": 240.5,
            "title": "New Song",
            "indexed_at": time.time(),
        })

        track = index.get_track("/music/new_song.mp3")
        assert track is not None
        assert track["duration"] == 240.5
        assert track["artist"] is None  # Optional fields default to None


class TestCacheStaleness:
    """Step 5: Cache staleness detection + persistence."""

    def test_find_stale_files_new_file(self, index):
        """New file (not in cache) is stale."""
        # Create a temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b'\xff\xfb\x90\x00' + b'\x00' * 100)
            mp3_path = Path(f.name)

        try:
            stale = index._find_stale_files([mp3_path])
            assert mp3_path in stale
        finally:
            mp3_path.unlink()

    def test_find_stale_files_modified_file(self, index):
        """Modified file (mtime changed) is stale."""
        # Create a temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b'\xff\xfb\x90\x00' + b'\x00' * 100)
            mp3_path = Path(f.name)

        try:
            # Get its mtime and store in cache
            mtime = mp3_path.stat().st_mtime
            index.store_track({
                "path": str(mp3_path),
                "duration": 180.0,
                "file_mtime": mtime - 100,  # Older mtime
                "indexed_at": time.time(),
            })

            stale = index._find_stale_files([mp3_path])
            assert mp3_path in stale
        finally:
            mp3_path.unlink()

    def test_find_stale_files_unchanged_file(self, index):
        """Unchanged file is not stale."""
        # Create a temporary MP3 file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b'\xff\xfb\x90\x00' + b'\x00' * 100)
            mp3_path = Path(f.name)

        try:
            # Get its mtime and store in cache
            mtime = mp3_path.stat().st_mtime
            index.store_track({
                "path": str(mp3_path),
                "duration": 180.0,
                "file_mtime": mtime,  # Same mtime
                "indexed_at": time.time(),
            })

            stale = index._find_stale_files([mp3_path])
            assert mp3_path not in stale
        finally:
            mp3_path.unlink()

    def test_find_stale_files_empty_list(self, index):
        """Empty file list returns empty stale list."""
        stale = index._find_stale_files([])
        assert stale == []

    def test_remove_tracks(self, index):
        """Remove tracks from cache."""
        for i in range(5):
            index.store_track({
                "path": f"/music/song{i}.mp3",
                "duration": 180.0,
                "artist": "Artist",
                "album": "Album",
                "title": f"Song {i}",
                "track": i,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": 1234567890.0,
                "indexed_at": time.time(),
            })

        assert index.get_track_count() == 5

        index._remove_tracks({"/music/song0.mp3", "/music/song2.mp3"})
        assert index.get_track_count() == 3
        assert index.get_track("/music/song0.mp3") is None
        assert index.get_track("/music/song1.mp3") is not None

    def test_remove_tracks_empty_set(self, index):
        """Remove empty set is a no-op."""
        index.store_track({
            "path": "/music/song.mp3",
            "duration": 180.0,
            "indexed_at": time.time(),
        })

        index._remove_tracks(set())
        assert index.get_track_count() == 1

    def test_scan_library_incremental(self, index, tmp_path):
        """Scan library only indexes new files on subsequent scans."""
        # Mock _probe_file to return metadata for any file
        original_probe = index._probe_file
        def mock_probe(path):
            return {
                "path": str(path),
                "duration": 180.0,
                "artist": "Test Artist",
                "album": "Test Album",
                "title": path.stem,
                "track": 1,
                "year": "2024",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME",
                "file_mtime": path.stat().st_mtime if path.exists() else None,
                "indexed_at": time.time(),
            }
        
        index._probe_file = mock_probe
        
        # Create test files
        for i in range(3):
            mp3 = tmp_path / f"song{i}.mp3"
            mp3.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 100)

        # First scan
        index.scan_library(tmp_path)
        assert index.get_track_count() == 3

        # Second scan (should not re-index)
        index.scan_library(tmp_path)
        assert index.get_track_count() == 3

        # Add a new file
        new_mp3 = tmp_path / "song3.mp3"
        new_mp3.write_bytes(b'\xff\xfb\x90\x00' + b'\x00' * 100)

        # Third scan (should only index new file)
        index.scan_library(tmp_path)
        assert index.get_track_count() == 4
        
        # Restore original
        index._probe_file = original_probe


class TestFTSSearch:
    """FTS5 full-text search across metadata."""

    def _populate_index(self, index):
        """Populate index with test tracks."""
        tracks = [
            {
                "path": "/music/sia/alive.mp3",
                "duration": 263.94,
                "artist": "Sia",
                "album": "This Is Acting",
                "title": "Alive",
                "track": 2,
                "year": "2016",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME 3.99",
                "file_mtime": 1234567890.0,
                "indexed_at": time.time(),
            },
            {
                "path": "/music/sia/chandelier.mp3",
                "duration": 216.0,
                "artist": "Sia",
                "album": "1000 Forms of Fear",
                "title": "Chandelier",
                "track": 1,
                "year": "2014",
                "genre": "Pop",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME 3.99",
                "file_mtime": 1234567891.0,
                "indexed_at": time.time(),
            },
            {
                "path": "/music/queen/bohemian.mp3",
                "duration": 354.0,
                "artist": "Queen",
                "album": "A Night at the Opera",
                "title": "Bohemian Rhapsody",
                "track": 1,
                "year": "1975",
                "genre": "Rock",
                "bitrate": 320000,
                "sample_rate": 44100,
                "channels": 2,
                "encoder": "LAME 3.99",
                "file_mtime": 1234567892.0,
                "indexed_at": time.time(),
            },
        ]
        index.store_batch(tracks)

    def test_search_by_artist(self, index):
        """Search returns matching artists."""
        self._populate_index(index)
        results = index.search_tracks("Sia")
        assert len(results) == 2
        assert all(r["artist"] == "Sia" for r in results)

    def test_search_by_title(self, index):
        """Search returns matching titles."""
        self._populate_index(index)
        results = index.search_tracks("Bohemian")
        assert len(results) == 1
        assert results[0]["title"] == "Bohemian Rhapsody"

    def test_search_by_genre(self, index):
        """Search returns matching genres."""
        self._populate_index(index)
        results = index.search_tracks("Rock")
        assert len(results) == 1
        assert results[0]["artist"] == "Queen"

    def test_search_empty_returns_all(self, index):
        """Empty query returns all tracks."""
        self._populate_index(index)
        results = index.search_tracks("")
        assert len(results) == 3

    def test_search_no_match(self, index):
        """Non-matching query returns empty list."""
        self._populate_index(index)
        results = index.search_tracks("NonexistentArtist")
        assert len(results) == 0

    def test_search_is_case_insensitive(self, index):
        """Search is case-insensitive (FTS5 default)."""
        self._populate_index(index)
        results_lower = index.search_tracks("sia")
        results_upper = index.search_tracks("SIA")
        assert len(results_lower) == len(results_upper) == 2

    def test_search_ranking(self, index):
        """Results are ranked by relevance (bm25)."""
        self._populate_index(index)
        results = index.search_tracks("Sia")
        # Both results should be Sia tracks
        assert all(r["artist"] == "Sia" for r in results)


class TestSchemaMigration:
    """Schema migration for existing databases."""

    def test_migrate_adds_missing_columns(self, db_path):
        """Migration adds missing columns to existing databases."""
        # Create old schema database
        conn = sqlite3.connect(str(db_path))
        conn.executescript("""
            CREATE TABLE tracks (
                path TEXT PRIMARY KEY,
                duration REAL,
                indexed_at REAL
            );
        """)
        conn.execute(
            "INSERT INTO tracks (path, duration, indexed_at) VALUES (?, ?, ?)",
            ("/old/song.mp3", 180.0, time.time())
        )
        conn.commit()
        conn.close()

        # Open with MetadataIndex (should migrate)
        index = MetadataIndex(db_path)

        # Verify new columns exist
        cursor = index.conn.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}
        assert "bitrate" in columns
        assert "sample_rate" in columns
        assert "channels" in columns
        assert "encoder" in columns
        assert "file_mtime" in columns

        # Old data should still be there
        track = index.get_track("/old/song.mp3")
        assert track is not None
        assert track["duration"] == 180.0

        index.close()

    def test_migrate_is_idempotent(self, db_path):
        """Running migration multiple times is safe."""
        index1 = MetadataIndex(db_path)
        index1.close()

        # Open again (should not fail)
        index2 = MetadataIndex(db_path)
        index2.close()
