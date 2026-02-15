import math
import uuid

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.database import get_db
from app.models import CreatePinnedContextRequest, PinnedContext

router = APIRouter(prefix='/api/conversations', tags=['pins'])

MAX_PINS_PER_CONVERSATION = 10
MAX_PINNED_TOKENS_PER_CONVERSATION = 2000


def _estimate_tokens(content: str) -> int:
    return max(1, math.ceil(len(content) / 4))


def _row_to_pin(row: dict) -> PinnedContext:
    return PinnedContext(
        id=row['id'],
        conversation_id=row['conversation_id'],
        source_message_id=row['source_message_id'],
        source_role=row['source_role'],
        content=row['content'],
        token_estimate=int(row['token_estimate']),
        created_at=row['created_at'],
    )


@router.get('/{conversation_id}/pins', response_model=list[PinnedContext])
async def list_pins(conversation_id: str) -> list[PinnedContext]:
    async with get_db() as conn:
        conversation_cursor = await conn.execute('SELECT id FROM conversations WHERE id = ?', (conversation_id,))
        conversation = await conversation_cursor.fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')

        cursor = await conn.execute(
            '''
            SELECT id, conversation_id, source_message_id, source_role, content, token_estimate, created_at
            FROM pinned_context
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            ''',
            (conversation_id,),
        )
        rows = await cursor.fetchall()

    return [_row_to_pin(dict(row)) for row in rows]


@router.post('/{conversation_id}/pins', response_model=PinnedContext, status_code=status.HTTP_201_CREATED)
async def create_pin(conversation_id: str, payload: CreatePinnedContextRequest) -> PinnedContext:
    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail='Pinned content cannot be empty')

    token_estimate = _estimate_tokens(content)

    async with get_db() as conn:
        conversation_cursor = await conn.execute('SELECT id FROM conversations WHERE id = ?', (conversation_id,))
        conversation = await conversation_cursor.fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')

        if payload.source_message_id:
            message_cursor = await conn.execute(
                'SELECT id, role FROM messages WHERE id = ? AND conversation_id = ?',
                (payload.source_message_id, conversation_id),
            )
            message = await message_cursor.fetchone()
            if message is None:
                raise HTTPException(status_code=400, detail='Source message does not belong to this conversation')

        limits_cursor = await conn.execute(
            '''
            SELECT COUNT(*) AS count, COALESCE(SUM(token_estimate), 0) AS total_tokens
            FROM pinned_context
            WHERE conversation_id = ?
            ''',
            (conversation_id,),
        )
        limits = await limits_cursor.fetchone()

        current_count = int(limits['count']) if limits is not None else 0
        current_tokens = int(limits['total_tokens']) if limits is not None else 0

        if current_count >= MAX_PINS_PER_CONVERSATION:
            raise HTTPException(
                status_code=400,
                detail=f'Pin limit reached ({MAX_PINS_PER_CONVERSATION} per conversation). Remove a pin and try again.',
            )

        if current_tokens + token_estimate > MAX_PINNED_TOKENS_PER_CONVERSATION:
            raise HTTPException(
                status_code=400,
                detail=(
                    f'Pinned context token budget exceeded (~{MAX_PINNED_TOKENS_PER_CONVERSATION} tokens per conversation). '
                    'Remove or shorten existing pins and try again.'
                ),
            )

        pin_id = str(uuid.uuid4())
        await conn.execute(
            '''
            INSERT INTO pinned_context (id, conversation_id, source_message_id, source_role, content, token_estimate)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                pin_id,
                conversation_id,
                payload.source_message_id,
                payload.source_role,
                content,
                token_estimate,
            ),
        )
        await conn.commit()

        cursor = await conn.execute(
            '''
            SELECT id, conversation_id, source_message_id, source_role, content, token_estimate, created_at
            FROM pinned_context
            WHERE id = ?
            ''',
            (pin_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail='Failed to create pin')

    return _row_to_pin(dict(row))


@router.delete('/{conversation_id}/pins', status_code=status.HTTP_204_NO_CONTENT)
async def delete_pin(conversation_id: str, pin_id: str = Query(min_length=1)) -> Response:
    async with get_db() as conn:
        conversation_cursor = await conn.execute('SELECT id FROM conversations WHERE id = ?', (conversation_id,))
        conversation = await conversation_cursor.fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail='Conversation not found')

        cursor = await conn.execute(
            'DELETE FROM pinned_context WHERE id = ? AND conversation_id = ?',
            (pin_id, conversation_id),
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail='Pin not found')

        await conn.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
