import json

from ..util import repair_text


class TerminateSignal(Exception):
    """Raised when the agent calls `terminate` with valid JSON."""

    def __init__(self, data: object) -> None:
        self.data = data


TOOL_DEF: dict = {
    "type": "function",
    "function": {
        "name": "terminate",
        "description": (
            "End the task and return the final result. "
            "The result MUST be a valid JSON string. "
            "If the JSON is invalid you will receive an error and must fix it before retrying."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "json_result": {
                    "type": "string",
                    "description": "The final result encoded as a valid JSON string.",
                },
            },
            "required": ["json_result"],
        },
    },
}


def handle(json_result: str | None = None, **kwargs: object) -> str:
    """Validate terminate payload and raise TerminateSignal on success."""
    if kwargs:
        got = ", ".join(sorted(kwargs.keys()))
        return (
            "Invalid terminate call: only `json_result` is allowed. "
            f"Got fields: {got}. Please call terminate again with a JSON string in `json_result`."
        )

    if json_result is None:
        return "Invalid terminate call: missing required field `json_result`."

    try:
        data = json.loads(repair_text(json_result))
    except json.JSONDecodeError as exc:
        return f"JSON syntax error — please fix and call terminate again: {exc}"

    raise TerminateSignal(data)
