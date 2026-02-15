from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.services.mcp_client import LoreMapClient
from app.services.producer import Producer

WORLDBUILDING_PROMPT = """## Worldbuilding Mode

You have access to a worldbuilding lore database for the Taito System
(a Lancer RPG setting). When the user discusses worldbuilding:

- Check the context package provided for existing lore and schemas
- Ask follow-up questions based on missing required fields
- Reference related entries naturally in conversation
- When enough information is gathered, present the entry for review
- Only save entries when the user explicitly approves

Entry types: location, faction, npc, event, culture
Each has specific required fields - check the schema before asking questions.

When presenting an entry for review, format it clearly with all fields
shown. Mark any fields you filled in vs. fields the user explicitly stated.

Do not invent lore. Only record what the user confirms as canon.
"""


@dataclass
class IntentResult:
    is_lore_related: bool
    intent_type: str
    entry_type: str | None
    confidence: float
    rationale: str


class Orchestrator:
    """Coordinates the dual-model pipeline for lore-aware conversations."""

    def __init__(self, producer: Producer | None = None, mcp_client: LoreMapClient | None = None):
        self.producer = producer or Producer()
        self.mcp = mcp_client or LoreMapClient()

    async def process_message(
        self,
        message: str,
        conversation: dict[str, Any] | None,
        history: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        intent = await self.detect_intent(message, history)
        if not intent.is_lore_related:
            return None

        context = await self.build_context(intent, message, history)
        return await self.compose_augmented_prompt(context)

    async def detect_intent(self, message: str, history: list[dict[str, str]]) -> IntentResult:
        history_summary = self._summarize_history(history)
        raw = await self.producer.classify_intent(message, history_summary)

        return IntentResult(
            is_lore_related=bool(raw.get('is_lore', False)),
            intent_type=str(raw.get('intent_type', 'other')),
            entry_type=(str(raw.get('entry_type')).strip() if raw.get('entry_type') else None),
            confidence=float(raw.get('confidence', 0.0) or 0.0),
            rationale=str(raw.get('rationale', '')),
        )

    async def build_context(
        self,
        intent: IntentResult,
        message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any]:
        entry_type = intent.entry_type or self._infer_entry_type(message)
        if not entry_type:
            return {
                'intent': intent.__dict__,
                'context_package': None,
                'error': 'No entry type detected for lore intent.',
            }

        context_package = await self.mcp.get_context_package(entry_type=entry_type, user_input=message)

        # Producer augments extracted fields + follow-up questions when available.
        schema = context_package.get('schema', {})
        producer_filled = await self.producer.extract_fields(message, schema)
        merged_filled = dict(context_package.get('filled_fields', {}))
        merged_filled.update(producer_filled)
        context_package['filled_fields'] = merged_filled

        required = schema.get('required_fields', []) if isinstance(schema, dict) else []
        missing = [field for field in required if not merged_filled.get(field)]
        context_package['missing_required'] = missing

        producer_questions = await self.producer.generate_follow_ups(schema, merged_filled, missing)
        questions = context_package.get('follow_up_questions', [])
        for question in producer_questions:
            if question not in questions:
                questions.append(question)
        context_package['follow_up_questions'] = questions[:10]

        return {
            'intent': intent.__dict__,
            'entry_type': entry_type,
            'context_package': context_package,
            'history_summary': self._summarize_history(history),
        }

    async def compose_augmented_prompt(self, context: dict[str, Any]) -> dict[str, Any]:
        context_package = context.get('context_package')
        if not context_package:
            return {'system_append': WORLDBUILDING_PROMPT, 'context_block': None}

        context_block = {
            'worldbuilding_mode': True,
            'entry_type': context.get('entry_type'),
            'intent': context.get('intent'),
            'context_package': context_package,
        }

        return {
            'system_append': WORLDBUILDING_PROMPT,
            'context_block': json.dumps(context_block, ensure_ascii=True),
        }

    @staticmethod
    def _summarize_history(history: list[dict[str, str]], max_messages: int = 8) -> str:
        recent = history[-max_messages:]
        lines: list[str] = []
        for msg in recent:
            role = msg.get('role', 'user')
            content = str(msg.get('content', '')).replace('\n', ' ').strip()
            if content:
                lines.append(f'{role}: {content[:220]}')
        return '\n'.join(lines)

    @staticmethod
    def _infer_entry_type(message: str) -> str | None:
        lowered = message.lower()
        for candidate in ['location', 'faction', 'npc', 'event', 'culture']:
            if f' {candidate}' in f' {lowered} ':
                return candidate
        return None
