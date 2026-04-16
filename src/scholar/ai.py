import os
import anthropic


async def explain_passage(context: dict) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"explanation": "ANTHROPIC_API_KEY environment variable is not set."}

    client = anthropic.AsyncAnthropic(api_key=api_key)

    parts = [f"Document: {context.get('doc_title', 'Unknown')}"]
    if context.get("reading_type"):
        parts.append(f"Reading type: {context['reading_type']}")
    if context.get("session_intention"):
        parts.append(f"Reading intention: {context['session_intention']}")
    if context.get("surrounding_text"):
        parts.append(f"\nPage context:\n{context['surrounding_text']}")
    parts.append(f"\nSelected passage:\n{context['selected_text']}")
    if context.get("user_interpretation"):
        parts.append(f"\nReader's interpretation:\n{context['user_interpretation']}")
    parts.append(
        "\nRespond as a thinking partner. Build on the reader's interpretation "
        "where possible. Be concise — two or three sentences."
    )

    message = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": "\n".join(parts)}],
    )

    return {"explanation": message.content[0].text}
