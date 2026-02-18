"""SQLite database setup and access."""

import aiosqlite

from config import settings

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS captures (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,           -- 'plex' or 'jellyfin'
    media_title TEXT NOT NULL,
    media_path TEXT NOT NULL,
    timestamp_seconds REAL NOT NULL,
    capture_type TEXT NOT NULL,     -- 'screenshot' or 'clip'
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size_bytes INTEGER DEFAULT 0,
    duration_seconds REAL,          -- only for clips
    status TEXT NOT NULL DEFAULT 'pending',  -- pending / complete / failed
    error_message TEXT,
    created_at TEXT NOT NULL
);
"""


async def init_db():
    async with aiosqlite.connect(settings.db_path) as db:
        await db.executescript(_DB_SCHEMA)
        await db.commit()


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(settings.db_path)
    db.row_factory = aiosqlite.Row
    return db