import json
import logging

from openai import OpenAI

from .tools import ALL_TOOLS, TerminateSignal, dispatch
from .util import (
    RetryState,
    fmt_tool_args,
    parse_plain_text_result,
    request_with_retry,
    tool_signature,
)

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

_DUPLICATE_CALL_THRESHOLD = 3
_MAX_DUPLICATE_REFUSALS = 8
_MAX_RATE_LIMIT_RETRIES_PER_MODEL = 6
_MAX_PLAIN_TEXT_ROUNDS = 3


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
    last_tool_signature: str | None = None
    duplicate_streak = 0
    duplicate_refusals = 0
    plain_text_rounds = 0
    retry_state = RetryState()

    while True:
        msg, current_model = request_with_retry(
            client=client,
            models=models,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
            logger=logger,
            state=retry_state,
            max_rate_limit_retries_per_model=_MAX_RATE_LIMIT_RETRIES_PER_MODEL,
        )

        # Log reasoning/thinking if the model returns it.
        reasoning = msg.get("reasoning")
        if reasoning:
            logger.debug("Model reasoning: %s", reasoning)
        # Build a clean assistant message (strip vendor-specific fields).
        assistant_msg: dict = {"role": "assistant", "content": msg.get("content", "")}
        if msg.get("tool_calls"):
            assistant_msg["tool_calls"] = msg["tool_calls"]
        messages.append(assistant_msg)

        if not msg.get("tool_calls"):
            plain_text_rounds += 1
            content = (msg.get("content") or "").strip()
            parsed_now = parse_plain_text_result(content)
            if parsed_now is not None:
                logger.info("Agent terminated from plain text JSON fallback.")
                return parsed_now

            if plain_text_rounds >= _MAX_PLAIN_TEXT_ROUNDS and content:
                logger.warning(
                    "Model returned plain text %s times without tool call; auto-terminating.",
                    plain_text_rounds,
                )
                logger.info("Agent terminated from plain text fallback.")
                return {"message": content}

            logger.debug("Model returned plain text — nudging to call terminate.")
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You must call the `terminate` tool now. "
                        'Arguments format: {"json_result": "{\\"key\\":\\"value\\"}"}. '
                        "Do not reply with plain text."
                    ),
                }
            )
            continue
        plain_text_rounds = 0

        for tc in msg["tool_calls"]:
            name = tc["function"]["name"]
            raw_arguments = tc["function"].get("arguments") or "{}"
            try:
                parsed_args = json.loads(raw_arguments)
            except json.JSONDecodeError:
                parsed_args = {"__invalid_json_arguments__": raw_arguments}

            logger.info("Tool call: %s(%s)", name, fmt_tool_args(parsed_args))

            if isinstance(parsed_args, dict):
                args = parsed_args
            else:
                msg_text = (
                    "Invalid tool arguments: expected a JSON object, "
                    f"got {type(parsed_args).__name__}. "
                    "Please call the tool again with an object payload."
                )
                logger.warning("%s | tool=%s", msg_text, name)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": msg_text,
                    }
                )
                continue

            signature = tool_signature(name, args)
            if signature == last_tool_signature:
                duplicate_streak += 1
            else:
                duplicate_streak = 1
                last_tool_signature = signature

            if duplicate_streak >= _DUPLICATE_CALL_THRESHOLD and name != "terminate":
                duplicate_refusals += 1
                refusal = (
                    "Rejected duplicate tool call: same tool+arguments was called repeatedly. "
                    "Please try a different URL/query/tool or terminate with current evidence."
                )
                logger.warning(
                    "Duplicate tool call refused (%s x%s): %s",
                    name,
                    duplicate_streak,
                    fmt_tool_args(args),
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": refusal,
                    }
                )
                if duplicate_refusals >= _MAX_DUPLICATE_REFUSALS:
                    raise RuntimeError(
                        "Too many duplicate tool calls were refused; aborting to prevent endless loop."
                    )
                continue

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
                    "tool_call_id": tc["id"],
                    "content": result,
                }
            )
