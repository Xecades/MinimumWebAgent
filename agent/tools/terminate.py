import json


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


def handle(json_result: str) -> str:
    """Validate JSON and raise TerminateSignal, or return an error string."""
    try:
        data = json.loads(json_result)
    except json.JSONDecodeError as exc:
        return f"JSON syntax error — please fix and call terminate again: {exc}"
    raise TerminateSignal(data)
