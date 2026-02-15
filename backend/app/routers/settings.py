import json
import time
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Response, status

from app.config import settings
from app.database import get_db
from app.models import (
    CreateSystemPromptRequest,
    ModelOption,
    SystemPrompt,
    UpdateSystemPromptRequest,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])

MODELS_CACHE_SECONDS = 3600
_models_cache: list[ModelOption] | None = None
_models_cache_expires_at = 0.0


def _decode_config_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _encode_config_value(value: Any) -> str:
    return json.dumps(value)


def _is_text_model(model_data: dict[str, Any]) -> bool:
    model_type = str(model_data.get("type", "")).lower()
    if model_type in {"chat", "text"}:
        return True

    architecture = model_data.get("architecture")
    if isinstance(architecture, dict):
        modality = str(architecture.get("modality", "")).lower()
        if "text" in modality or "chat" in modality:
            return True

    input_modalities = model_data.get("input_modalities")
    if isinstance(input_modalities, list) and any("text" in str(item).lower() for item in input_modalities):
        return True

    output_modalities = model_data.get("output_modalities")
    if isinstance(output_modalities, list) and any("text" in str(item).lower() for item in output_modalities):
        return True

    return False


@router.get("", response_model=dict[str, Any])
async def get_settings() -> dict[str, Any]:
    async with get_db() as conn:
        cursor = await conn.execute("SELECT key, value FROM config ORDER BY key ASC")
        rows = await cursor.fetchall()

    return {row["key"]: _decode_config_value(row["value"]) for row in rows}


@router.patch("", status_code=status.HTTP_204_NO_CONTENT)
async def update_settings(payload: dict[str, Any]) -> Response:
    if not payload:
        raise HTTPException(status_code=400, detail="No settings provided")

    async with get_db() as conn:
        for key, value in payload.items():
            await conn.execute(
                """
                INSERT INTO config (key, value)
                VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, _encode_config_value(value)),
            )
        await conn.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/models", response_model=list[ModelOption])
async def get_models() -> list[ModelOption]:
    global _models_cache
    global _models_cache_expires_at

    now = time.time()
    if _models_cache is not None and now < _models_cache_expires_at:
        return _models_cache

    if not settings.OPENROUTER_API_KEY:
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {settings.OPENROUTER_API_KEY}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "Nexus Assistant",
    }

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(f"{settings.OPENROUTER_BASE_URL}/models", headers=headers)

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail="Failed to fetch models from OpenRouter")

    payload = response.json()
    models_data = payload.get("data", []) if isinstance(payload, dict) else []

    options: list[ModelOption] = []
    for model_data in models_data:
        if not isinstance(model_data, dict):
            continue
        if not _is_text_model(model_data):
            continue

        model_id = str(model_data.get("id", "")).strip()
        if not model_id:
            continue

        name = str(model_data.get("name") or model_data.get("canonical_name") or model_id)
        options.append(ModelOption(id=model_id, name=name))

    _models_cache = options
    _models_cache_expires_at = now + MODELS_CACHE_SECONDS
    return options


@router.get("/prompts", response_model=list[SystemPrompt])
async def get_system_prompts() -> list[SystemPrompt]:
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            SELECT id, name, content, is_default
            FROM system_prompts
            ORDER BY is_default DESC, name ASC
            """
        )
        rows = await cursor.fetchall()

    return [
        SystemPrompt(
            id=row["id"],
            name=row["name"],
            content=row["content"],
            is_default=bool(row["is_default"]),
        )
        for row in rows
    ]


@router.post("/prompts", response_model=SystemPrompt, status_code=status.HTTP_201_CREATED)
async def create_system_prompt(payload: CreateSystemPromptRequest) -> SystemPrompt:
    prompt_id = str(uuid.uuid4())

    async with get_db() as conn:
        if payload.is_default:
            await conn.execute("UPDATE system_prompts SET is_default = 0")

        await conn.execute(
            """
            INSERT INTO system_prompts (id, name, content, is_default)
            VALUES (?, ?, ?, ?)
            """,
            (prompt_id, payload.name, payload.content, int(payload.is_default)),
        )
        await conn.commit()

        cursor = await conn.execute(
            "SELECT id, name, content, is_default FROM system_prompts WHERE id = ?",
            (prompt_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create system prompt")

    return SystemPrompt(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        is_default=bool(row["is_default"]),
    )


@router.patch("/prompts/{prompt_id}", response_model=SystemPrompt)
async def update_system_prompt(prompt_id: str, payload: UpdateSystemPromptRequest) -> SystemPrompt:
    if payload.name is None and payload.content is None and payload.is_default is None:
        raise HTTPException(status_code=400, detail="No updates provided")

    async with get_db() as conn:
        if payload.is_default:
            await conn.execute("UPDATE system_prompts SET is_default = 0")

        cursor = await conn.execute(
            """
            UPDATE system_prompts
            SET
                name = COALESCE(?, name),
                content = COALESCE(?, content),
                is_default = CASE WHEN ? IS NULL THEN is_default ELSE ? END,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                payload.name,
                payload.content,
                payload.is_default,
                int(payload.is_default) if payload.is_default is not None else None,
                prompt_id,
            ),
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="System prompt not found")

        await conn.commit()

        select_cursor = await conn.execute(
            "SELECT id, name, content, is_default FROM system_prompts WHERE id = ?",
            (prompt_id,),
        )
        row = await select_cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="System prompt not found")

    return SystemPrompt(
        id=row["id"],
        name=row["name"],
        content=row["content"],
        is_default=bool(row["is_default"]),
    )


@router.delete("/prompts/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_system_prompt(prompt_id: str) -> Response:
    async with get_db() as conn:
        cursor = await conn.execute(
            "SELECT is_default FROM system_prompts WHERE id = ?",
            (prompt_id,),
        )
        row = await cursor.fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="System prompt not found")

        if bool(row["is_default"]):
            raise HTTPException(status_code=400, detail="Default system prompt cannot be deleted")

        await conn.execute("DELETE FROM system_prompts WHERE id = ?", (prompt_id,))
        await conn.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
