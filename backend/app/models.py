from typing import Literal

from pydantic import BaseModel, Field


class Conversation(BaseModel):
    id: str
    title: str
    model: str
    updated_at: str
    message_count: int = 0


class Message(BaseModel):
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    model: str | None = None
    created_at: str


class ConversationDetail(BaseModel):
    conversation: Conversation
    messages: list[Message]


class CreateConversationRequest(BaseModel):
    model: str | None = None
    system_prompt_id: str | None = None


class UpdateConversationRequest(BaseModel):
    title: str | None = None
    model: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class SystemPrompt(BaseModel):
    id: str
    name: str
    content: str
    is_default: bool


class CreateSystemPromptRequest(BaseModel):
    name: str = Field(min_length=1)
    content: str = Field(min_length=1)
    is_default: bool = False


class UpdateSystemPromptRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    is_default: bool | None = None


class ModelOption(BaseModel):
    id: str
    name: str
