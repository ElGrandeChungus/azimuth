import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from app.config import settings


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT 'New Conversation',
    model TEXT NOT NULL DEFAULT '',
    system_prompt_id TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (system_prompt_id) REFERENCES system_prompts(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS system_prompts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    content TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pinned_context (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    source_message_id TEXT,
    source_role TEXT CHECK(source_role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    token_estimate INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (source_message_id) REFERENCES messages(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation
    ON messages(conversation_id, created_at);

CREATE INDEX IF NOT EXISTS idx_conversations_updated
    ON conversations(updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_pins_conversation_created
    ON pinned_context(conversation_id, created_at DESC);
"""


async def _connect() -> aiosqlite.Connection:
    db_path = Path(settings.DATABASE_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(db_path.as_posix())
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys = ON")
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

        await conn.execute(
            """
            INSERT OR IGNORE INTO system_prompts (id, name, content, is_default)
            VALUES (?, ?, ?, ?)
            """,
            (
                "default",
                "Default",
                "You are Azi, a helpful personal AI assistant. Be conversational, concise, and direct. If you do not know something, say so.",
                1,
            ),
        )

        await conn.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            ("default_model", '"anthropic/claude-sonnet-4.5"'),
        )
        await conn.execute(
            "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
            ("theme", '"dark"'),
        )

        await conn.commit()


def init_db_sync() -> None:
    asyncio.run(init_db())
