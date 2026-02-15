import asyncio
import json
import uuid
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.database import get_db
from app.models import SendMessageRequest
from app.services.ai import generate_title, stream_chat
from app.services.mcp_client import LoreMapClient
from app.services.orchestrator import Orchestrator
from app.services.prompts import build_messages

router = APIRouter(prefix='/api/conversations', tags=['messages'])

DEFAULT_SYSTEM_PROMPT = (
    'You are Azi, a helpful personal AI assistant. Be conversational, concise, '
    'and direct. If you do not know something, say so.'
)

orchestrator = Orchestrator()
loremap_client = LoreMapClient()

APPROVAL_KEYWORDS = {
    'approve',
    'approved',
    'looks good',
    'ship it',
    'save it',
    'commit it',
    'canon',
    'lock it in',
}


def _sse_event(payload: dict[str, str]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _is_approval_message(message: str) -> bool:
    lowered = message.lower()
    return any(keyword in lowered for keyword in APPROVAL_KEYWORDS)


def _extract_context_payload(augmented: dict[str, Any] | None) -> dict[str, Any] | None:
    if not augmented:
        return None

    raw = augmented.get('context_block')
    if not raw or not isinstance(raw, str):
        return None

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None

    return parsed if isinstance(parsed, dict) else None


def _normalize_entry_name(value: str) -> str:
    cleaned = value.strip().strip('"\'')
    lowered = cleaned.lower()
    for sep in [' who ', ' that ', ' which ']:
        idx = lowered.find(sep)
        if idx != -1:
            cleaned = cleaned[:idx]
            lowered = cleaned.lower()
    return cleaned.strip(' .,!?:;')


def _build_create_entry_payload(augmented: dict[str, Any] | None) -> dict[str, Any] | None:
    context_root = _extract_context_payload(augmented)
    if not context_root:
        return None

    package = context_root.get('context_package')
    if not isinstance(package, dict):
        return None

    missing_required = package.get('missing_required')
    if isinstance(missing_required, list) and missing_required:
        return None

    filled = package.get('filled_fields')
    if not isinstance(filled, dict):
        return None

    entry_type = context_root.get('entry_type') or filled.get('type')
    if not entry_type:
        return None

    name = _normalize_entry_name(str(filled.get('name', '')).strip())
    category = str(filled.get('category', '')).strip()
    status = str(filled.get('status', '')).strip()
    content = str(filled.get('content', '')).strip()
    summary = str(filled.get('summary', '')).strip() or content[:220]

    if not all([name, category, status, content]):
        return None

    metadata = filled.get('metadata') if isinstance(filled.get('metadata'), dict) else {}

    references_raw = filled.get('references')
    if not isinstance(references_raw, list):
        references_raw = package.get('suggested_references', [])

    references: list[dict[str, Any]] = []
    if isinstance(references_raw, list):
        for ref in references_raw:
            if not isinstance(ref, dict):
                continue
            target_slug = str(ref.get('target_slug', '')).strip()
            target_type = str(ref.get('target_type', '')).strip()
            relationship = str(ref.get('relationship', 'related_to')).strip() or 'related_to'
            if target_slug and target_type:
                references.append(
                    {
                        'target_slug': target_slug,
                        'target_type': target_type,
                        'relationship': relationship,
                    }
                )

    payload: dict[str, Any] = {
        'type': str(entry_type),
        'name': name,
        'category': category,
        'status': status,
        'summary': summary,
        'content': content,
        'metadata': metadata,
        'references': references,
    }

    parent_slug = filled.get('parent_slug')
    if isinstance(parent_slug, str) and parent_slug.strip():
        payload['parent_slug'] = parent_slug.strip()

    return payload


async def _autotitle_conversation(conversation_id: str, first_message: str, model: str) -> None:
    try:
        title = await generate_title(first_message, model)
        if not title:
            return

        async with get_db() as conn:
            await conn.execute(
                '''
                UPDATE conversations
                SET title = ?, updated_at = datetime('now')
                WHERE id = ? AND (title = 'New Conversation' OR title = '')
                ''',
                (title, conversation_id),
            )
            await conn.commit()
    except Exception:
        return


@router.post('/{conversation_id}/messages')
async def send_message(conversation_id: str, payload: SendMessageRequest):
    user_content = payload.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail='Message content cannot be empty')

    async with get_db() as conn:
        conversation_cursor = await conn.execute(
            'SELECT id, model, system_prompt_id FROM conversations WHERE id = ?',
            (conversation_id,),
        )
        conversation = await conversation_cursor.fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')

        count_cursor = await conn.execute(
            'SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?',
            (conversation_id,),
        )
        count_row = await count_cursor.fetchone()
        first_exchange = (count_row['count'] if count_row is not None else 0) == 0

        user_message_id = str(uuid.uuid4())
        await conn.execute(
            '''
            INSERT INTO messages (id, conversation_id, role, content, model)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (user_message_id, conversation_id, 'user', user_content, None),
        )
        await conn.commit()

        history_cursor = await conn.execute(
            '''
            SELECT role, content
            FROM messages
            WHERE conversation_id = ? AND id != ?
            ORDER BY created_at ASC
            ''',
            (conversation_id, user_message_id),
        )
        history_rows = await history_cursor.fetchall()

        system_prompt_content = DEFAULT_SYSTEM_PROMPT
        system_prompt_id = conversation['system_prompt_id']
        if system_prompt_id:
            prompt_cursor = await conn.execute(
                'SELECT content FROM system_prompts WHERE id = ?',
                (system_prompt_id,),
            )
            prompt_row = await prompt_cursor.fetchone()
            if prompt_row is not None:
                system_prompt_content = prompt_row['content']
        else:
            default_prompt_cursor = await conn.execute(
                '''
                SELECT content FROM system_prompts
                WHERE is_default = 1
                ORDER BY updated_at DESC
                LIMIT 1
                '''
            )
            default_prompt_row = await default_prompt_cursor.fetchone()
            if default_prompt_row is not None:
                system_prompt_content = default_prompt_row['content']

    selected_model = conversation['model'] or settings.DEFAULT_MODEL
    history_messages = [{'role': row['role'], 'content': row['content']} for row in history_rows]

    augmented_context: dict[str, Any] | None = None
    try:
        augmented_context = await orchestrator.process_message(
            user_content,
            dict(conversation),
            history_messages,
        )
    except Exception:
        augmented_context = None

    if augmented_context and augmented_context.get('system_append'):
        system_prompt_content = f"{system_prompt_content}\n\n{augmented_context['system_append']}"

    llm_messages = await build_messages(history_messages, system_prompt_content)

    if augmented_context and augmented_context.get('context_block'):
        llm_messages.append({'role': 'system', 'content': str(augmented_context['context_block'])})

    llm_messages.append({'role': 'user', 'content': user_content})

    approval_result: dict[str, Any] | None = None
    if _is_approval_message(user_content):
        create_payload = _build_create_entry_payload(augmented_context)
        if create_payload:
            try:
                approval_result = await loremap_client.create_entry(**create_payload)
            except Exception:
                approval_result = None

    assistant_message_id = str(uuid.uuid4())
    response_parts: list[str] = []

    async def event_stream() -> AsyncGenerator[str, None]:
        if approval_result is not None:
            entry = approval_result.get('entry', {}) if isinstance(approval_result, dict) else {}
            entry_name = str(entry.get('name', 'Entry'))
            entry_slug = str(entry.get('slug', ''))
            confirm_text = f"Saved lore entry '{entry_name}' ({entry_slug})."
            response_parts.append(confirm_text)
            yield _sse_event({'type': 'delta', 'content': confirm_text})
        else:
            try:
                async for delta in stream_chat(llm_messages, selected_model):
                    response_parts.append(delta)
                    yield _sse_event({'type': 'delta', 'content': delta})
            except Exception as exc:
                yield _sse_event({'type': 'error', 'message': str(exc)})
                return

        full_response = ''.join(response_parts)

        try:
            async with get_db() as conn:
                await conn.execute(
                    '''
                    INSERT INTO messages (id, conversation_id, role, content, model)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    (
                        assistant_message_id,
                        conversation_id,
                        'assistant',
                        full_response,
                        selected_model,
                    ),
                )
                await conn.execute(
                    "UPDATE conversations SET updated_at = datetime('now') WHERE id = ?",
                    (conversation_id,),
                )
                await conn.commit()
        except Exception as exc:
            yield _sse_event({'type': 'error', 'message': str(exc)})
            return

        if first_exchange:
            asyncio.create_task(_autotitle_conversation(conversation_id, user_content, selected_model))

        yield _sse_event(
            {
                'type': 'done',
                'message_id': assistant_message_id,
                'model': selected_model,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )
