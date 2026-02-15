from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/lore.db')

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    type TEXT NOT NULL CHECK(type IN (
        'location', 'faction', 'npc', 'event', 'culture'
    )),
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL,
    parent_slug TEXT,
    summary TEXT,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS "references" (
    id TEXT PRIMARY KEY,
    source_slug TEXT NOT NULL,
    target_slug TEXT NOT NULL,
    target_type TEXT NOT NULL,
    relationship TEXT,
    FOREIGN KEY (source_slug) REFERENCES entries(slug) ON DELETE CASCADE,
    UNIQUE(source_slug, target_slug)
);

CREATE TABLE IF NOT EXISTS lexicon (
    id TEXT PRIMARY KEY,
    term TEXT UNIQUE NOT NULL,
    definition TEXT NOT NULL,
    see_also TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS threads (
    id TEXT PRIMARY KEY,
    entity_a TEXT NOT NULL,
    entity_b TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    description TEXT NOT NULL,
    relevant_entries TEXT DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS campaign_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    slug, name, summary, content,
    content='entries',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, slug, name, summary, content)
    VALUES (new.rowid, new.slug, new.name, new.summary, new.content);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, slug, name, summary, content)
    VALUES ('delete', old.rowid, old.slug, old.name, old.summary, old.content);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, slug, name, summary, content)
    VALUES ('delete', old.rowid, old.slug, old.name, old.summary, old.content);
    INSERT INTO entries_fts(rowid, slug, name, summary, content)
    VALUES (new.rowid, new.slug, new.name, new.summary, new.content);
END;

CREATE INDEX IF NOT EXISTS idx_entries_type ON entries(type);
CREATE INDEX IF NOT EXISTS idx_entries_parent ON entries(parent_slug);
CREATE INDEX IF NOT EXISTS idx_refs_source ON "references"(source_slug);
CREATE INDEX IF NOT EXISTS idx_refs_target ON "references"(target_slug);
"""


async def _connect() -> aiosqlite.Connection:
    db_path = Path(DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path.as_posix())
    conn.row_factory = aiosqlite.Row
    await conn.execute('PRAGMA journal_mode=WAL')
    await conn.execute('PRAGMA foreign_keys = ON')
    return conn


@asynccontextmanager
async def get_db() -> aiosqlite.Connection:
    conn = await _connect()
    try:
        yield conn
    finally:
        await conn.close()


async def init_db() -> None:
    async with get_db() as conn:
        await conn.executescript(SCHEMA_SQL)
        await conn.commit()


def init_db_sync() -> None:
    asyncio.run(init_db())


if __name__ == '__main__':
    init_db_sync()