from __future__ import annotations

import json
import re
from typing import Any

from openai import AsyncOpenAI

from app.config import settings


class Producer:
    """Cheap model for background classification and extraction."""

    def __init__(self, model: str | None = None):
        self.client = AsyncOpenAI(
            base_url=settings.OPENROUTER_BASE_URL,
            api_key=settings.OPENROUTER_API_KEY,
        )
        self.model = (model or settings.PRODUCER_MODEL).strip()

    async def classify_intent(self, message: str, history_summary: str = '') -> dict[str, Any]:
        prompt = (
            'Classify whether the user message is lore-related for a worldbuilding database. '
            'Return strict JSON with keys: is_lore (bool), intent_type (create|update|query|other), '
            'entry_type (location|faction|npc|event|culture|null), confidence (0-1), rationale (short string).'
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': prompt},
                    {
                        'role': 'user',
                        'content': json.dumps({'message': message, 'history_summary': history_summary}),
                    },
                ],
                response_format={'type': 'json_object'},
                extra_headers={
                    'HTTP-Referer': 'http://localhost:3000',
                    'X-Title': 'Azimuth Assistant',
                },
            )

            raw = (response.choices[0].message.content or '').strip()
            parsed = self._safe_json(raw)
            if parsed:
                return {
                    'is_lore': bool(parsed.get('is_lore', False)),
                    'intent_type': str(parsed.get('intent_type', 'other')),
                    'entry_type': parsed.get('entry_type'),
                    'confidence': float(parsed.get('confidence', 0.0) or 0.0),
                    'rationale': str(parsed.get('rationale', '')),
                }
        except Exception:
            pass

        return self._heuristic_intent(message)

    async def extract_fields(self, message: str, schema: dict[str, Any]) -> dict[str, Any]:
        prompt = (
            'Extract structured fields from user text using the provided schema. '
            'Return strict JSON with key filled_fields containing only fields present in user text. '
            'Do not hallucinate values.'
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': prompt},
                    {
                        'role': 'user',
                        'content': json.dumps({'message': message, 'schema': schema}),
                    },
                ],
                response_format={'type': 'json_object'},
                extra_headers={
                    'HTTP-Referer': 'http://localhost:3000',
                    'X-Title': 'Azimuth Assistant',
                },
            )

            raw = (response.choices[0].message.content or '').strip()
            parsed = self._safe_json(raw)
            if parsed and isinstance(parsed.get('filled_fields'), dict):
                return parsed['filled_fields']
        except Exception:
            pass

        return {}

    async def generate_follow_ups(
        self,
        schema: dict[str, Any],
        filled: dict[str, Any],
        missing: list[str],
    ) -> list[str]:
        prompt = (
            'Generate concise follow-up questions for missing required fields. '
            'Return strict JSON with key questions as an array of short strings.'
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': prompt},
                    {
                        'role': 'user',
                        'content': json.dumps(
                            {'schema': schema, 'filled_fields': filled, 'missing_required': missing}
                        ),
                    },
                ],
                response_format={'type': 'json_object'},
                extra_headers={
                    'HTTP-Referer': 'http://localhost:3000',
                    'X-Title': 'Azimuth Assistant',
                },
            )

            raw = (response.choices[0].message.content or '').strip()
            parsed = self._safe_json(raw)
            if parsed and isinstance(parsed.get('questions'), list):
                return [str(q).strip() for q in parsed['questions'] if str(q).strip()]
        except Exception:
            pass

        return [f'Can you provide {field}?' for field in missing]

    @staticmethod
    def _safe_json(raw: str) -> dict[str, Any] | None:
        if not raw:
            return None
        try:
            obj = json.loads(raw)
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _heuristic_intent(message: str) -> dict[str, Any]:
        text = message.lower()
        lore_terms = ['npc', 'faction', 'location', 'event', 'culture', 'lore', 'worldbuilding', 'canon']
        entry_type = None
        for candidate in ['location', 'faction', 'npc', 'event', 'culture']:
            if re.search(rf'\b{candidate}\b', text):
                entry_type = candidate
                break

        is_lore = any(term in text for term in lore_terms)
        intent_type = 'query'
        if any(token in text for token in ['create', 'add', 'make', 'invent', 'new']):
            intent_type = 'create'
        elif any(token in text for token in ['update', 'change', 'edit', 'revise']):
            intent_type = 'update'

        return {
            'is_lore': is_lore,
            'intent_type': intent_type if is_lore else 'other',
            'entry_type': entry_type,
            'confidence': 0.4,
            'rationale': 'heuristic fallback',
        }
