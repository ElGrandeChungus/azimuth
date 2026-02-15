from __future__ import annotations

import json
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.config import settings


class LoreMapClient:
    """MCP client for calling Lore Map server tools."""

    def __init__(self, server_url: str | None = None):
        self.server_url = (server_url or settings.LOREMAP_MCP_URL).strip()

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = arguments or {}
        async with streamable_http_client(self.server_url) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, payload)
                structured = getattr(result, 'structuredContent', None)
                if isinstance(structured, dict):
                    return structured

                content = getattr(result, 'content', None) or []
                if content:
                    text = getattr(content[0], 'text', None)
                    if text:
                        try:
                            return json.loads(text)
                        except json.JSONDecodeError:
                            return {'raw': text}

                return {'raw': str(result)}

    async def create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return await self.call_tool('create_entry', kwargs)

    async def get_entry(self, slug: str) -> dict[str, Any]:
        return await self.call_tool('get_entry', {'slug': slug})

    async def search(self, query: str, type: str | None = None, limit: int = 10) -> dict[str, Any]:
        return await self.call_tool('search_entries', {'query': query, 'type': type, 'limit': limit})

    async def get_context_package(
        self,
        entry_type: str,
        user_input: str,
        existing_slug: str | None = None,
    ) -> dict[str, Any]:
        return await self.call_tool(
            'get_context_package',
            {
                'entry_type': entry_type,
                'user_input': user_input,
                'existing_slug': existing_slug,
            },
        )

    async def find_related(self, slug: str, limit: int = 5) -> dict[str, Any]:
        return await self.call_tool('find_related', {'slug': slug, 'limit': limit})
