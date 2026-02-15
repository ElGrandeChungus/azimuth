import uuid

from fastapi import APIRouter, HTTPException, Response, status

from app.database import get_db
from app.models import (
    Conversation,
    ConversationDetail,
    CreateConversationRequest,
    Message,
    UpdateConversationRequest,
)
from app.services.config_store import get_default_model

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


@router.get("", response_model=list[Conversation])
async def list_conversations() -> list[Conversation]:
    async with get_db() as conn:
        cursor = await conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.model,
                c.updated_at,
                (
                    SELECT COUNT(*)
                    FROM messages m
                    WHERE m.conversation_id = c.id
                ) AS message_count
            FROM conversations c
            ORDER BY c.updated_at DESC
            """
        )
        rows = await cursor.fetchall()

    return [Conversation(**dict(row)) for row in rows]


@router.post("", response_model=Conversation, status_code=status.HTTP_201_CREATED)
async def create_conversation(payload: CreateConversationRequest) -> Conversation:
    conversation_id = str(uuid.uuid4())

    async with get_db() as conn:
        conversation_model = (payload.model or "").strip()
        if not conversation_model:
            conversation_model = await get_default_model(conn=conn)

        await conn.execute(
            """
            INSERT INTO conversations (id, title, model, system_prompt_id)
            VALUES (?, ?, ?, ?)
            """,
            (
                conversation_id,
                "New Conversation",
                conversation_model,
                payload.system_prompt_id,
            ),
        )
        await conn.commit()

        cursor = await conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.model,
                c.updated_at,
                (
                    SELECT COUNT(*)
                    FROM messages m
                    WHERE m.conversation_id = c.id
                ) AS message_count
            FROM conversations c
            WHERE c.id = ?
            """,
            (conversation_id,),
        )
        row = await cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=500, detail="Failed to create conversation")

    return Conversation(**dict(row))


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str) -> ConversationDetail:
    async with get_db() as conn:
        conversation_cursor = await conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.model,
                c.updated_at,
                (
                    SELECT COUNT(*)
                    FROM messages m
                    WHERE m.conversation_id = c.id
                ) AS message_count
            FROM conversations c
            WHERE c.id = ?
            """,
            (conversation_id,),
        )
        conversation_row = await conversation_cursor.fetchone()

        if conversation_row is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages_cursor = await conn.execute(
            """
            SELECT id, conversation_id, role, content, model, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            """,
            (conversation_id,),
        )
        message_rows = await messages_cursor.fetchall()

    return ConversationDetail(
        conversation=Conversation(**dict(conversation_row)),
        messages=[Message(**dict(row)) for row in message_rows],
    )


@router.patch("/{conversation_id}", response_model=Conversation)
async def update_conversation(conversation_id: str, payload: UpdateConversationRequest) -> Conversation:
    if payload.title is None and payload.model is None:
        raise HTTPException(status_code=400, detail="No updates provided")

    async with get_db() as conn:
        cursor = await conn.execute(
            """
            UPDATE conversations
            SET
                title = COALESCE(?, title),
                model = COALESCE(?, model),
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (payload.title, payload.model, conversation_id),
        )

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await conn.commit()

        select_cursor = await conn.execute(
            """
            SELECT
                c.id,
                c.title,
                c.model,
                c.updated_at,
                (
                    SELECT COUNT(*)
                    FROM messages m
                    WHERE m.conversation_id = c.id
                ) AS message_count
            FROM conversations c
            WHERE c.id = ?
            """,
            (conversation_id,),
        )
        row = await select_cursor.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return Conversation(**dict(row))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(conversation_id: str) -> Response:
    async with get_db() as conn:
        cursor = await conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")

        await conn.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)
