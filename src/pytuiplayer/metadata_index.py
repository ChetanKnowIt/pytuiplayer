"""Metadata indexing for pytuiplayer.

Builds and maintains a persistent index of the local music library
using mutagen for fast metadata extraction and SQLite for storage.
"""

import sqlite3
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    indexed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_tracks_artist ON tracks(artist);
CREATE INDEX IF NOT EXISTS idx_tracks_album ON tracks(album);
CREATE INDEX IF NOT EXISTS idx_tracks_title ON tracks(title);
"""


class MetadataIndex:
    """Persistent metadata index backed by SQLite.

    Scans a music library recursively using pathlib.Path.rglob()
    and probes file metadata using mutagen (fast, already a dependency).
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self):
        """Close the database connection."""
        self.conn.close()

    def scan_library(self, root: Path, progress_callback=None):
        """Scan a music library directory and index all MP3 files.

        Uses mutagen for fast metadata extraction.
        Respects existing entries to avoid re-indexing.
        """
        # Find all MP3 files
        start = time.time()
        files = list(root.rglob("*.mp3"))
        total = len(files)
        if total == 0:
            logger.warning("No MP3 files found in %s", root)
            return

        logger.info("Found %d MP3 files in %s", total, root)

        # Filter out already-indexed files
        indexed = self._get_indexed_paths()
        new_files = [f for f in files if str(f) not in indexed]
        logger.info("Already indexed: %d, New: %d", len(indexed), len(new_files))

        if not new_files:
            return

        # Phase 1: Probe all files in parallel (fast, no DB writes)
        metadata_list = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {
                executor.submit(self._probe_file, f): f
                for f in new_files
            }
            for future in as_completed(futures):
                path = futures[future]
                try:
                    metadata = future.result()
                    if metadata:
                        metadata_list.append(metadata)
                    if progress_callback:
                        progress_callback(len(metadata_list), len(new_files))
                except Exception as e:
                    logger.warning("Failed to index %s: %s", path, e)

        # Phase 2: Batch insert all metadata (single transaction, fast)
        if metadata_list:
            self._store_batch(metadata_list)
            logger.info("Indexed %d new tracks in %.2fs", len(metadata_list), time.time() - start)

    def _probe_file(self, path: Path) -> dict | None:
        """Probe a single file for metadata using mutagen.

        Returns dict with duration, artist, album, title, track, year, genre.
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

    def _store_batch(self, metadata_list: list[dict]):
        """Store multiple metadata entries in a single transaction (fast)."""
        data = [
            (
                m["path"], m["duration"], m["artist"], m["album"],
                m["title"], m["track"], m["year"], m["genre"], m["indexed_at"],
            )
            for m in metadata_list
        ]
        self.conn.executemany(
            """
            INSERT OR REPLACE INTO tracks
            (path, duration, artist, album, title, track, year, genre, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            data,
        )
        self.conn.commit()

    def _store_metadata(self, metadata: dict):
        """Store metadata in the database."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO tracks
            (path, duration, artist, album, title, track, year, genre, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metadata["path"],
                metadata["duration"],
                metadata["artist"],
                metadata["album"],
                metadata["title"],
                metadata["track"],
                metadata["year"],
                metadata["genre"],
                metadata["indexed_at"],
            ),
        )
        self.conn.commit()

    def _get_indexed_paths(self) -> set:
        """Get set of already indexed file paths."""
        cursor = self.conn.execute("SELECT path FROM tracks")
        return {row[0] for row in cursor.fetchall()}

    def get_all_tracks(self) -> list[dict]:
        """Get all indexed tracks."""
        cursor = self.conn.execute(
            "SELECT path, duration, artist, album, title, track, year, genre "
            "FROM tracks ORDER BY artist, album, track"
        )
        columns = ["path", "duration", "artist", "album", "title", "track", "year", "genre"]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_track(self, path: str) -> dict | None:
        """Get metadata for a specific track."""
        cursor = self.conn.execute(
            "SELECT path, duration, artist, album, title, track, year, genre "
            "FROM tracks WHERE path = ?",
            (path,),
        )
        row = cursor.fetchone()
        if row:
            columns = ["path", "duration", "artist", "album", "title", "track", "year", "genre"]
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
