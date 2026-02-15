from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.services.mcp_client import LoreMapClient

router = APIRouter(prefix='/api/lore', tags=['lore'])

loremap_client = LoreMapClient()


class CreateLoreEntryRequest(BaseModel):
    type: str
    name: str
    category: str
    status: str
    summary: str
    content: str
    metadata: dict[str, Any] | None = None
    references: list[dict[str, Any]] | None = None
    parent_slug: str | None = None


class UpdateLoreEntryRequest(BaseModel):
    updates: dict[str, Any]


@router.get('/entries')
async def list_entries(
    type: str | None = None,
    parent_slug: str | None = None,
) -> dict[str, Any]:
    try:
        return await loremap_client.call_tool('list_entries', {'type': type, 'parent_slug': parent_slug})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get('/entries/{slug}')
async def get_entry(slug: str) -> dict[str, Any]:
    try:
        return await loremap_client.get_entry(slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post('/entries', status_code=status.HTTP_201_CREATED)
async def create_entry(payload: CreateLoreEntryRequest) -> dict[str, Any]:
    try:
        return await loremap_client.create_entry(**payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch('/entries/{slug}')
async def update_entry(slug: str, payload: UpdateLoreEntryRequest) -> dict[str, Any]:
    try:
        return await loremap_client.call_tool('update_entry', {'slug': slug, 'updates': payload.updates})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete('/entries/{slug}')
async def delete_entry(slug: str) -> dict[str, Any]:
    try:
        return await loremap_client.call_tool('delete_entry', {'slug': slug})
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get('/search')
async def search_entries(
    q: str = Query(..., min_length=1),
    type: str | None = None,
    limit: int = Query(10, ge=1, le=50),
) -> dict[str, Any]:
    try:
        return await loremap_client.search(query=q, type=type, limit=limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get('/schemas/{entry_type}')
async def get_schema(entry_type: str) -> dict[str, Any]:
    try:
        return await loremap_client.call_tool('get_schema', {'type': entry_type})
    except Exception as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get('/health')
async def lore_health() -> dict[str, str]:
    try:
        await loremap_client.call_tool('get_schema', {'type': 'npc'})
        return {'status': 'ok'}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f'MCP unavailable: {exc}') from exc
