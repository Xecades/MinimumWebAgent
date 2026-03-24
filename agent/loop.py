import json
import logging

from openai import OpenAI, RateLimitError

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


def run(
    client: OpenAI,
    models: list[str],
    query: str,
    logger: logging.Logger,
) -> object:
    """Run the agent loop and return the parsed JSON result."""
    model_idx = 0
    logger.info("Starting agent | model=%s", models[model_idx])
    logger.info("User prompt: %s", query)

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]

    while True:
        current_model = models[model_idx]
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                tools=ALL_TOOLS,
                tool_choice="auto",
            )
        except RateLimitError:
            if model_idx + 1 < len(models):
                model_idx += 1
                logger.warning(
                    "Rate-limited on %s — falling back to %s",
                    current_model,
                    models[model_idx],
                )
                continue
            logger.error("All models exhausted (rate limit). Giving up.")
            raise

        msg = response.choices[0].message

        # Log reasoning/thinking if the model returns it.
        reasoning = getattr(msg, "reasoning", None)
        if reasoning:
            logger.debug("Model reasoning: %s", reasoning)
        # Build a clean assistant message (strip vendor-specific fields).
        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

        if not msg.tool_calls:
            logger.debug("Model returned plain text — nudging to call terminate.")
            messages.append(
                {
                    "role": "user",
                    "content": "Please call the `terminate` tool with your JSON result to finish.",
                }
            )
            continue

        for tc in msg.tool_calls:
            name = tc.function.name
            args = json.loads(tc.function.arguments)
            logger.info("Tool call: %s(%s)", name, _fmt_args(args))

            try:
                result = dispatch(name, args)
            except TerminateSignal as sig:
                logger.info(
                    "Agent terminated. Result: %s", json.dumps(sig.data, ensure_ascii=False)
                )
                return sig.data

            logger.debug("Tool result [%s]:\n%s", name, result)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )


def _fmt_args(args: dict) -> str:
    """Compact single-line representation of tool arguments for logging."""
    parts = []
    for k, v in args.items():
        v_str = repr(v) if not isinstance(v, str) else f"{v!r}"
        if len(v_str) > 80:
            v_str = v_str[:77] + "..."
        parts.append(f"{k}={v_str}")
    return ", ".join(parts)
