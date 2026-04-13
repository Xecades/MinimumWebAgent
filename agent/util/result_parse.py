import json
import re

from .normalize import repair_text

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def parse_plain_text_result(content: str) -> object | None:
    candidate = _extract_json_candidate(repair_text(content))
    if candidate is None:
        return None
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    if isinstance(parsed, dict):
        inner = parsed.get("json_result")
        if isinstance(inner, str):
            try:
                return json.loads(inner)
            except json.JSONDecodeError:
                return parsed
    return parsed


def _extract_json_candidate(content: str) -> str | None:
    text = content.strip()
    if not text:
        return None

    m = _JSON_FENCE_RE.search(text)
    if m:
        return m.group(1).strip()

    if text.startswith("{") or text.startswith("["):
        return text

    start_obj = text.find("{")
    end_obj = text.rfind("}")
    if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
        return text[start_obj : end_obj + 1]

    start_arr = text.find("[")
    end_arr = text.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return text[start_arr : end_arr + 1]

    return None
