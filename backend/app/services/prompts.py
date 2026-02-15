from typing import Any


async def build_messages(
    conversation_messages: list[dict[str, str]],
    system_prompt_content: str,
    pinned_context: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    """Assemble the messages array for the AI call."""
    messages = [{'role': 'system', 'content': system_prompt_content}]

    if pinned_context:
        lines = ['Pinned Context Snippets:']
        for index, item in enumerate(pinned_context, start=1):
            content = str(item.get('content', '')).strip()
            if not content:
                continue
            lines.append(f'{index}. {content}')

        if len(lines) > 1:
            lines.append('Treat pinned snippets as high-priority reference context for this conversation.')
            messages.append({'role': 'system', 'content': '\n'.join(lines)})

    for msg in conversation_messages:
        messages.append({'role': msg['role'], 'content': msg['content']})

    return messages
