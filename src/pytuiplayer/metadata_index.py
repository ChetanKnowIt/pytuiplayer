"""Metadata indexing for pytuiplayer.

Builds and maintains a persistent index of the local music library
using mutagen for fast metadata extraction and SQLite for storage.
"""

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from mutagen import File as MutagenFile

from pytuiplayer.logging_config import get_logger

logger = get_logger("metadata_index")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    path TEXT PRIMARY KEY,
    duration REAL,
    artist TEXT,
    album TEXT,
    title TEXT,
    track INTEGER,
    year TEXT,
    genre TEXT,
    bitrate INTEGER,
    sample_rate INTEGER,
    channels INTEGER,
    encoder TEXT,
    file_mtime REAL,
    indexed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
CREATE INDEX IF NOT EXISTS idx_tracks_mtime ON tracks(file_mtime);

-- FTS5 full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    path UNINDEXED,
    artist,
    album,
    title,
    genre,
    content='tracks',
    content_rowid='rowid'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS tracks_ai AFTER INSERT ON tracks BEGIN
    INSERT INTO tracks_fts(rowid, path, artist, album, title, genre)
    VALUES (new.rowid, new.path, new.artist, new.album, new.title, new.genre);
END;

CREATE TRIGGER IF NOT EXISTS tracks_ad AFTER DELETE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, path, artist, album, title, genre)
    VALUES ('delete', old.rowid, old.path, old.artist, old.album, old.title, old.genre);
END;

CREATE TRIGGER IF NOT EXISTS tracks_au AFTER UPDATE ON tracks BEGIN
    INSERT INTO tracks_fts(tracks_fts, rowid, path, artist, album, title, genre)
    VALUES ('delete', old.rowid, old.path, old.artist, old.album, old.title, old.genre);
    INSERT INTO tracks_fts(rowid, path, artist, album, title, genre)
    VALUES (new.rowid, new.path, new.artist, new.album, new.title, new.genre);
END;
"""


class MetadataIndex:
    """Persistent metadata index backed by SQLite.

    Scans a music library recursively using pathlib.Path.rglob()
    and probes file metadata using mutagen (fast, already a dependency).
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        
        # Check if table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'"
        )
        table_exists = cursor.fetchone() is not None
        
        if table_exists:
            # Table exists with potentially old schema - migrate
            self._migrate_schema()
        else:
            # Create fresh schema
            self.conn.executescript(SCHEMA)
        
        self.conn.commit()

    def _migrate_schema(self):
        """Add missing columns to existing databases (forward-compatible).

        Handles migration from old schema versions by adding new columns
        if they don't already exist.
        """
        # Check if table exists
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'"
        )
        if not cursor.fetchone():
            # Table doesn't exist, create it with full schema
            self.conn.executescript(SCHEMA)
            return

        # Table exists, check for missing columns
        cursor = self.conn.execute("PRAGMA table_info(tracks)")
        columns = {row[1] for row in cursor.fetchall()}

        migrations = [
            ("bitrate", "INTEGER"),
            ("sample_rate", "INTEGER"),
            ("channels", "INTEGER"),
            ("encoder", "TEXT"),
            ("file_mtime", "REAL"),
            ("artist", "TEXT"),
            ("album", "TEXT"),
            ("title", "TEXT"),
            ("track", "INTEGER"),
            ("year", "TEXT"),
            ("genre", "TEXT"),
            ("indexed_at", "REAL"),
        ]

        for col_name, col_type in migrations:
            if col_name not in columns:
                try:
                    self.conn.execute(f"ALTER TABLE tracks ADD COLUMN {col_name} {col_type}")
                except sqlite3.OperationalError:
                    pass  # Column already exists or other error

        # Migrate FTS index (may not exist in old databases)
        self._migrate_fts()

    def _migrate_fts(self):
        """Create FTS index if it doesn't exist."""
        cursor = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tracks_fts'"
        )
        if cursor.fetchone():
            return  # FTS table already exists

        try:
            # Create FTS table and triggers
            self.conn.executescript("""
                CREATE VIRTUAL TABLE tracks_fts USING fts5(
                    path UNINDEXED,
                    artist,
                    album,
                    title,
                    genre,
                    content='tracks',
                    content_rowid='rowid'
                );

                CREATE TRIGGER tracks_ai AFTER INSERT ON tracks BEGIN
                    INSERT INTO tracks_fts(rowid, path, artist, album, title, genre)
                    VALUES (new.rowid, new.path, new.artist, new.album, new.title, new.genre);
                END;

                CREATE TRIGGER tracks_ad AFTER DELETE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, path, artist, album, title, genre)
                    VALUES ('delete', old.rowid, old.path, old.artist, old.album, old.title, old.genre);
                END;

                CREATE TRIGGER tracks_au AFTER UPDATE ON tracks BEGIN
                    INSERT INTO tracks_fts(tracks_fts, rowid, path, artist, album, title, genre)
                    VALUES ('delete', old.rowid, old.path, old.artist, old.album, old.title, old.genre);
                    INSERT INTO tracks_fts(rowid, path, artist, album, title, genre)
                    VALUES (new.rowid, new.path, new.artist, new.album, new.title, new.genre);
                END;
            """)

            # Populate FTS with existing data
            self.rebuild_fts_index()
        except sqlite3.OperationalError as e:
            logger.debug("FTS migration failed: %s", e)

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def scan_library(self, root: Path, progress_callback=None):
        """Scan a music library directory and index all MP3 files.

        Uses mutagen for fast metadata extraction.
        Handles incremental indexing:
        - New files: probe and insert
        - Modified files: probe and update (detected via mtime)
        - Deleted files: remove from cache
        """
        start = time.time()

        # Find all MP3 files on disk
        files = list(root.rglob("*.mp3"))
        total = len(files)
        if total == 0:
            logger.warning("No MP3 files found in %s", root)
            return

        logger.info("Found %d MP3 files in %s", total, root)

        # Get current state from cache
        current_paths = {str(f) for f in files}
        cached = self._get_indexed_paths()

        # Detect stale entries (file modified since last index)
        stale_files = self._find_stale_files(files)

        # Files to index: new + stale
        new_files = [f for f in files if str(f) not in cached]
        files_to_index = new_files + stale_files
        logger.info("New: %d, Stale: %d, Total to index: %d",
                     len(new_files), len(stale_files), len(files_to_index))

        if not files_to_index:
            # Still need to remove deleted files from cache
            deleted = cached - current_paths
            if deleted:
                self._remove_tracks(deleted)
                logger.info("Removed %d deleted tracks from cache", len(deleted))
            return

        # Phase 1: Probe all files in parallel
        metadata_list = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._probe_file, f): f
                for f in files_to_index
            }
            for future in as_completed(futures):
                path = futures[future]
                try:
                    metadata = future.result()
                    if metadata:
                        metadata_list.append(metadata)
                    if progress_callback:
                        progress_callback(len(metadata_list), len(files_to_index))
                except Exception as e:
                    logger.warning("Failed to index %s: %s", path, e)

        # Phase 2: Batch insert all metadata
        if metadata_list:
            self._store_batch(metadata_list)

        # Phase 3: Remove deleted files from cache
        deleted = cached - current_paths
        if deleted:
            self._remove_tracks(deleted)

        logger.info("Indexed %d tracks in %.2fs", len(metadata_list), time.time() - start)

    def _find_stale_files(self, files: list[Path]) -> list[Path]:
        """Find files that have been modified since last indexing.

        Uses a single SQL query for all mtimes (efficient).
        """
        if not files:
            return []

        # Get all cached mtimes in one query
        paths = [str(f) for f in files]
        placeholders = ",".join("?" * len(paths))
        cursor = self.conn.execute(
            f"SELECT path, file_mtime FROM tracks WHERE path IN ({placeholders})",
            paths,
        )
        cached_mtimes = {row[0]: row[1] for row in cursor.fetchall()}

        # Compare mtimes
        stale = []
        for f in files:
            try:
                mtime = f.stat().st_mtime
                cached_mtime = cached_mtimes.get(str(f))
                if cached_mtime is None or mtime > cached_mtime:
                    stale.append(f)
            except Exception:
                pass  # File might be inaccessible
        return stale

    def _remove_tracks(self, paths: set):
        """Remove tracks from the database."""
        if not paths:
            return
        placeholders = ",".join("?" * len(paths))
        self.conn.execute(
            f"DELETE FROM tracks WHERE path IN ({placeholders})",
            list(paths),
        )
        self.conn.commit()

    def _probe_file(self, path: Path) -> dict | None:
        """Probe a single file for metadata using mutagen.

        Returns dict with duration, artist, album, title, track, year, genre,
        bitrate, sample_rate, channels, encoder, file_mtime.
        """
        try:
            audio = MutagenFile(str(path))
            if audio is None:
                return None

            info = audio.info
            tags = audio.tags or {}

            return {
                "path": str(path),
                "duration": info.length if info else None,
                "artist": self._get_tag(tags, ["artist", "TPE1"]),
                "album": self._get_tag(tags, ["album", "TALB"]),
                "title": self._get_tag(tags, ["title", "TIT2"]),
                "track": self._parse_track(self._get_tag(tags, ["tracknumber", "TRCK"])),
                "year": self._get_tag(tags, ["date", "TDRC", "year"]),
                "genre": self._get_tag(tags, ["genre", "TCON"]),
                "bitrate": getattr(info, "bitrate", None),
                "sample_rate": getattr(info, "sample_rate", None),
                "channels": getattr(info, "channels", None),
                "encoder": getattr(info, "encoder_info", None),
                "file_mtime": path.stat().st_mtime if path.exists() else None,
                "indexed_at": time.time(),
            }
        except Exception as e:
            logger.debug("mutagen probe failed for %s: %s", path, e)
            return None

    def _get_tag(self, tags: dict, keys: list[str]) -> str | None:
        """Get a tag value from multiple possible keys."""
        for key in keys:
            value = tags.get(key)
            if value:
                if isinstance(value, list):
                    value = value[0]
                return str(value).strip() or None
        return None

    def _parse_track(self, value: str | None) -> int | None:
        """Parse track number from string (may be '3/12' format)."""
        if not value:
            return None
        try:
            # Handle "3/12" format
            return int(str(value).split("/")[0])
        except (ValueError, IndexError):
            return None

    def store_batch(self, metadata_list: list[dict]):
        """Store multiple metadata entries in a single transaction (fast).
        
        This is the public API for batch inserts.
        """
        self._store_batch(metadata_list)

    def _store_batch(self, metadata_list: list[dict]):
        """Store multiple metadata entries in a single transaction (fast)."""
        data = [
            (
                m.get("path"), m.get("duration"), m.get("artist"), m.get("album"),
                m.get("title"), m.get("track"), m.get("year"), m.get("genre"),
                m.get("bitrate"), m.get("sample_rate"), m.get("channels"), m.get("encoder"),
                m.get("file_mtime"), m.get("indexed_at"),
            )
            for m in metadata_list
        ]
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO tracks
            (path, duration, artist, album, title, track, year, genre,
             bitrate, sample_rate, channels, encoder, file_mtime, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )
        self.conn.commit()

    def store_track(self, metadata: dict):
        """Store a single track's metadata in the cache.

        This is the public API for storing individual track metadata.
        """
        self._store_metadata(metadata)

    def _store_metadata(self, metadata: dict):
        """Store metadata in the database."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, duration, artist, album, title, track, year, genre,
             bitrate, sample_rate, channels, encoder, file_mtime, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata.get("path"),
                metadata.get("duration"),
                metadata.get("artist"),
                metadata.get("album"),
                metadata.get("title"),
                metadata.get("track"),
                metadata.get("year"),
                metadata.get("genre"),
                metadata.get("bitrate"),
                metadata.get("sample_rate"),
                metadata.get("channels"),
                metadata.get("encoder"),
                metadata.get("file_mtime"),
                metadata.get("indexed_at"),
            ),
        )
        self.conn.commit()

    def _get_indexed_paths(self) -> set:
        """Get set of already indexed file paths."""
        cursor = self.conn.execute("SELECT path FROM tracks")
        return {row[0] for row in cursor.fetchall()}

    def get_tracks_bulk(self, paths: list[str]) -> list[dict | None]:
        """Get metadata for multiple tracks efficiently.

        Uses a single SQL query with WHERE path IN (...).
        Returns results in the same order as input paths.
        """
        if not paths:
            return []
        placeholders = ",".join("?" * len(paths))
        cursor = self.conn.execute(
            f"""SELECT path, duration, artist, album, title, track, year, genre,
                bitrate, sample_rate, channels, encoder
                FROM tracks WHERE path IN ({placeholders})
                ORDER BY artist, album, track""",
            paths,
        )
        columns = [
            "path", "duration", "artist", "album", "title", "track", "year", "genre",
            "bitrate", "sample_rate", "channels", "encoder",
        ]
        path_to_track = {
            row[0]: dict(zip(columns, row, strict=True))
            for row in cursor.fetchall()
        }
        return [path_to_track.get(p) for p in paths]

    def get_all_tracks(self) -> list[dict]:
        """Get all indexed tracks."""
        cursor = self.conn.execute(
            "SELECT path, duration, artist, album, title, track, year, genre, "
            "bitrate, sample_rate, channels, encoder "
            "FROM tracks ORDER BY artist, album, track"
        )
        columns = ["path", "duration", "artist", "album", "title", "track", "year", "genre",
                   "bitrate", "sample_rate", "channels", "encoder"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_track(self, path: str) -> dict | None:
        """Get metadata for a specific track."""
        cursor = self.conn.execute(
            "SELECT path, duration, artist, album, title, track, year, genre, "
            "bitrate, sample_rate, channels, encoder "
            "FROM tracks WHERE path = ?",
            (path,),
        )
        row = cursor.fetchone()
        if row:
            columns = ["path", "duration", "artist", "album", "title", "track", "year", "genre",
                       "bitrate", "sample_rate", "channels", "encoder"]
            return dict(zip(columns, row))
        return None

    def get_total_duration(self) -> float:
        """Get total duration of all indexed tracks in seconds."""
        cursor = self.conn.execute("SELECT SUM(duration) FROM tracks WHERE duration IS NOT NULL")
        result = cursor.fetchone()[0]
        return result or 0.0

    def get_track_count(self) -> int:
        """Get total number of indexed tracks."""
        cursor = self.conn.execute("SELECT COUNT(*) FROM tracks")
        return cursor.fetchone()[0]

    def search_tracks(self, query: str) -> list[dict]:
        """Full-text search across artist, album, title, genre.

        Uses SQLite FTS5 for lightning-fast search.
        Returns list of matching tracks with rank ordering.
        """
        if not query or not query.strip():
            return self.get_all_tracks()

        # Use FTS5 for fast full-text search
        # bm25() returns relevance score (lower = more relevant)
        try:
            cursor = self.conn.execute(
                """
                SELECT t.path, t.duration, t.artist, t.album, t.title,
                       t.track, t.year, t.genre, t.bitrate, t.sample_rate,
                       t.channels, t.encoder
                FROM tracks_fts fts
                JOIN tracks t ON t.path = fts.path
                WHERE tracks_fts MATCH ?
                ORDER BY bm25(tracks_fts) ASC
                LIMIT 1000
                """,
                (query.strip(),),
            )
            columns = [
                "path", "duration", "artist", "album", "title",
                "track", "year", "genre", "bitrate", "sample_rate",
                "channels", "encoder",
            ]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        except sqlite3.OperationalError as e:
            logger.debug("FTS search failed: %s", e)
            return []

    def rebuild_fts_index(self):
        """Rebuild FTS index from scratch (useful for migration)."""
        try:
            # Check if FTS table exists
            cursor = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='tracks_fts'"
            )
            if not cursor.fetchone():
                return  # FTS table doesn't exist, nothing to rebuild

            # Use INSERT OR REPLACE to rebuild (handles external content tables)
            self.conn.execute(
                """
                INSERT INTO tracks_fts(tracks_fts) VALUES('rebuild')
                """
            )
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.debug("FTS rebuild failed: %s", e)
