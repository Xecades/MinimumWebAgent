from openai import OpenAI


def create_chat_completion_streamed(
    client: OpenAI,
    model: str,
    messages: list[dict],
    tools: list[dict],
    tool_choice: str,
) -> dict:
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        tool_choice=tool_choice,
        stream=True,
    )

    content_parts: list[str] = []
    reasoning_parts: list[str] = []
    tool_calls_by_index: dict[int, dict] = {}

    for chunk in stream:
        if not chunk.choices:
            continue
        choice = chunk.choices[0]
        delta = choice.delta
        if delta is None:
            continue

        if delta.content:
            content_parts.append(delta.content)

        reasoning = getattr(delta, "reasoning", None)
        if isinstance(reasoning, str) and reasoning:
            reasoning_parts.append(reasoning)

        for tc in delta.tool_calls or []:
            idx = tc.index if tc.index is not None else 0
            entry = tool_calls_by_index.setdefault(
                idx,
                {
                    "id": tc.id or f"tool_{idx}",
                    "type": "function",
                    "function": {"name": "", "arguments": ""},
                },
            )
            if tc.id:
                entry["id"] = tc.id

            fn = tc.function
            if fn is None:
                continue
            if fn.name:
                entry["function"]["name"] = fn.name
            if fn.arguments:
                entry["function"]["arguments"] += fn.arguments

    ordered_tool_calls = [tool_calls_by_index[k] for k in sorted(tool_calls_by_index.keys())]
    return {
        "content": "".join(content_parts),
        "reasoning": "".join(reasoning_parts) if reasoning_parts else None,
        "tool_calls": ordered_tool_calls,
    }
