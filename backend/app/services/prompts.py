async def build_messages(
    conversation_messages: list[dict[str, str]],
    system_prompt_content: str,
) -> list[dict[str, str]]:
    """Assemble the messages array for the AI call."""
    messages = [{"role": "system", "content": system_prompt_content}]
    for msg in conversation_messages:
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages
