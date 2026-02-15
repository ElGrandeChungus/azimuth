import json
from typing import Any

import aiosqlite

from app.config import settings
from app.database import get_db


def _decode_config_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


async def get_config_value(
    key: str,
    default: Any = None,
    conn: aiosqlite.Connection | None = None,
) -> Any:
    if conn is not None:
        cursor = await conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = await cursor.fetchone()
    else:
        async with get_db() as db_conn:
            cursor = await db_conn.execute("SELECT value FROM config WHERE key = ?", (key,))
            row = await cursor.fetchone()

    if row is None:
        return default

    return _decode_config_value(row["value"])


async def get_default_model(conn: aiosqlite.Connection | None = None) -> str:
    raw_value = await get_config_value("default_model", settings.DEFAULT_MODEL, conn=conn)
    resolved = str(raw_value).strip() if raw_value is not None else ""
    return resolved or settings.DEFAULT_MODEL
