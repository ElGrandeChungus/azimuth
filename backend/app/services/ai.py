from openai import AsyncOpenAI

from app.config import settings

client = AsyncOpenAI(
    base_url=settings.OPENROUTER_BASE_URL,
    api_key=settings.OPENROUTER_API_KEY,
)


async def stream_chat(messages: list[dict[str, str]], model: str):
    """Yield content deltas from OpenRouter streaming response."""
    stream = await client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        extra_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Nexus Assistant",
        },
    )
    async for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def generate_title(first_user_message: str, model: str) -> str:
    """Generate a short conversation title (max 5 words)."""
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "Create a concise conversation title using at most 5 words. Return only the title text.",
            },
            {"role": "user", "content": first_user_message},
        ],
        extra_headers={
            "HTTP-Referer": "http://localhost:3000",
            "X-Title": "Nexus Assistant",
        },
    )
    raw = (response.choices[0].message.content or "").strip()
    title = " ".join(raw.replace("\n", " ").split())
    if not title:
        return "New Conversation"
    words = title.split()
    return " ".join(words[:5])
