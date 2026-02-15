import asyncio
import json
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.config import settings
from app.database import get_db
from app.models import SendMessageRequest
from app.services.ai import generate_title, stream_chat
from app.services.prompts import build_messages

router = APIRouter(prefix="/api/conversations", tags=["messages"])

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful personal AI assistant. Be conversational, concise, "
    "and direct. If you do not know something, say so."
)


def _sse_event(payload: dict[str, str]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


async def _autotitle_conversation(conversation_id: str, first_message: str, model: str) -> None:
    try:
        title = await generate_title(first_message, model)
        if not title:
            return

        async with get_db() as conn:
            await conn.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = datetime('now')
                WHERE id = ? AND (title = 'New Conversation' OR title = '')
                """,
                (title, conversation_id),
            )
            await conn.commit()
    except Exception:
        # Title generation failure should not break message streaming.
        return


@router.post("/{conversation_id}/messages")
async def send_message(conversation_id: str, payload: SendMessageRequest):
    user_content = payload.content.strip()
    if not user_content:
        raise HTTPException(status_code=400, detail="Message content cannot be empty")

    async with get_db() as conn:
        conversation_cursor = await conn.execute(
            "SELECT id, model, system_prompt_id FROM conversations WHERE id = ?",
            (conversation_id,),
        )
        conversation = await conversation_cursor.fetchone()
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        count_cursor = await conn.execute(
            "SELECT COUNT(*) AS count FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )
        count_row = await count_cursor.fetchone()
        first_exchange = (count_row["count"] if count_row is not None else 0) == 0

        user_message_id = str(uuid.uuid4())
        await conn.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, model)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_message_id, conversation_id, "user", user_content, None),
        )
        await conn.commit()

        history_cursor = await conn.execute(
            """
            SELECT role, content
            FROM messages
            WHERE conversation_id = ? AND id != ?
            ORDER BY created_at ASC
            """,
            (conversation_id, user_message_id),
        )
        history_rows = await history_cursor.fetchall()

        system_prompt_content = DEFAULT_SYSTEM_PROMPT
        system_prompt_id = conversation["system_prompt_id"]
        if system_prompt_id:
            prompt_cursor = await conn.execute(
                "SELECT content FROM system_prompts WHERE id = ?",
                (system_prompt_id,),
            )
            prompt_row = await prompt_cursor.fetchone()
            if prompt_row is not None:
                system_prompt_content = prompt_row["content"]
        else:
            default_prompt_cursor = await conn.execute(
                """
                SELECT content FROM system_prompts
                WHERE is_default = 1
                ORDER BY updated_at DESC
                LIMIT 1
                """
            )
            default_prompt_row = await default_prompt_cursor.fetchone()
            if default_prompt_row is not None:
                system_prompt_content = default_prompt_row["content"]

    selected_model = conversation["model"] or settings.DEFAULT_MODEL
    history_messages = [{"role": row["role"], "content": row["content"]} for row in history_rows]
    llm_messages = await build_messages(history_messages, system_prompt_content)
    llm_messages.append({"role": "user", "content": user_content})

    assistant_message_id = str(uuid.uuid4())
    response_parts: list[str] = []

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            async for delta in stream_chat(llm_messages, selected_model):
                response_parts.append(delta)
                yield _sse_event({"type": "delta", "content": delta})
        except Exception as exc:
            yield _sse_event({"type": "error", "message": str(exc)})
            return

        full_response = "".join(response_parts)

        try:
            async with get_db() as conn:
                await conn.execute(
                    """
                    INSERT INTO messages (id, conversation_id, role, content, model)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        assistant_message_id,
                        conversation_id,
                        "assistant",
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
            yield _sse_event({"type": "error", "message": str(exc)})
            return

        if first_exchange:
            asyncio.create_task(_autotitle_conversation(conversation_id, user_content, selected_model))

        yield _sse_event(
            {
                "type": "done",
                "message_id": assistant_message_id,
                "model": selected_model,
            }
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
