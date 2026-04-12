import json
import logging
import time

from openai import APIStatusError, NotFoundError, OpenAI, RateLimitError

from .tools import ALL_TOOLS, TerminateSignal, dispatch
from .util import compute_backoff_seconds, fmt_tool_args, tool_signature

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
    rate_limit_retries = 0

    while True:
        current_model = models[model_idx]
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                tools=ALL_TOOLS,
                tool_choice="auto",
            )
            rate_limit_retries = 0
        except RateLimitError as err:
            rate_limit_retries += 1
            if rate_limit_retries <= _MAX_RATE_LIMIT_RETRIES_PER_MODEL:
                sleep_s = compute_backoff_seconds(err, rate_limit_retries)
                logger.warning(
                    "Rate-limited on %s (retry %s/%s) — backing off %.1fs",
                    current_model,
                    rate_limit_retries,
                    _MAX_RATE_LIMIT_RETRIES_PER_MODEL,
                    sleep_s,
                )
                time.sleep(sleep_s)
                continue
            if model_idx + 1 < len(models):
                model_idx += 1
                rate_limit_retries = 0
                logger.warning(
                    "Rate-limited on %s after retries — falling back to %s",
                    current_model,
                    models[model_idx],
                )
                continue
            logger.error("All models exhausted (rate limit after retries). Giving up.")
            raise
        except NotFoundError:
            if model_idx + 1 < len(models):
                model_idx += 1
                rate_limit_retries = 0
                logger.warning(
                    "Model unavailable on %s — falling back to %s",
                    current_model,
                    models[model_idx],
                )
                continue
            logger.error("All models exhausted (unavailable). Giving up.")
            raise
        except APIStatusError as err:
            if err.status_code == 429:
                rate_limit_retries += 1
                if rate_limit_retries <= _MAX_RATE_LIMIT_RETRIES_PER_MODEL:
                    sleep_s = compute_backoff_seconds(err, rate_limit_retries)
                    logger.warning(
                        "429 on %s (retry %s/%s) — backing off %.1fs",
                        current_model,
                        rate_limit_retries,
                        _MAX_RATE_LIMIT_RETRIES_PER_MODEL,
                        sleep_s,
                    )
                    time.sleep(sleep_s)
                    continue
                if model_idx + 1 < len(models):
                    model_idx += 1
                    rate_limit_retries = 0
                    logger.warning(
                        "429 on %s after retries — falling back to %s",
                        current_model,
                        models[model_idx],
                    )
                    continue
                logger.error("All models exhausted (429 after retries). Giving up.")
                raise
            if err.status_code == 404 and model_idx + 1 < len(models):
                model_idx += 1
                rate_limit_retries = 0
                logger.warning(
                    "Model returned 404 on %s — falling back to %s",
                    current_model,
                    models[model_idx],
                )
                continue
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
            raw_arguments = tc.function.arguments or "{}"
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
                        "tool_call_id": tc.id,
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
                        "tool_call_id": tc.id,
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
                    "tool_call_id": tc.id,
                    "content": result,
                }
            )
