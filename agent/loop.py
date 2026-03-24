import json

from openai import OpenAI

from .tools import ALL_TOOLS, TerminateSignal, dispatch

_SYSTEM_PROMPT = """\
You are a research agent with access to web search, browser control, and HTTP fetch tools.
Use them to answer the user's query thoroughly.

Rules:
- Always call `terminate` when you have a final answer.
- The argument to `terminate` must be a valid JSON string.
- If `terminate` returns a JSON error, fix the JSON and try again.
- Prefer `search_web` for quick lookups; use `browser_*` tools when you need to interact
  with a specific page (fill forms, click buttons, etc.); use `http_fetch` for raw APIs.
"""


def run(client: OpenAI, model: str, query: str) -> object:
    """Run the agent loop and return the parsed JSON result."""
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    while True:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        # Append assistant message (tool_calls or text).
        messages.append(msg.model_dump(exclude_unset=True))

        if not msg.tool_calls:
            # Model produced plain text instead of a tool call — nudge it.
            messages.append({
                "role": "user",
                "content": "Please call the `terminate` tool with your JSON result to finish.",
            })
            continue

        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments)
            try:
                result = dispatch(tc.function.name, args)
            except TerminateSignal as sig:
                return sig.data

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
