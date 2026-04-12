from . import browser, http, search, terminate
from .terminate import TerminateSignal

# All tool schemas passed to the LLM.
ALL_TOOLS: list[dict] = [
    *browser.TOOL_DEFS,
    http.TOOL_DEF,
    search.TOOL_DEF,
    terminate.TOOL_DEF,
]


def dispatch(name: str, args: dict) -> str:
    """Route a tool call by name and return the string result."""
    if name in browser.HANDLERS:
        try:
            return browser.HANDLERS[name](**args)
        except TypeError as exc:
            return f"Invalid arguments for {name}: {exc}. Please fix args and retry."
    match name:
        case "http_fetch":
            try:
                return http.handle(**args)
            except TypeError as exc:
                return f"Invalid arguments for {name}: {exc}. Please fix args and retry."
        case "search_web":
            try:
                return search.handle(**args)
            except TypeError as exc:
                return f"Invalid arguments for {name}: {exc}. Please fix args and retry."
        case "terminate":
            try:
                return terminate.handle(**args)  # may raise TerminateSignal
            except TypeError as exc:
                return f"Invalid arguments for {name}: {exc}. Please fix args and retry."
        case _:
            return f"Unknown tool: {name!r}"


__all__ = ["ALL_TOOLS", "dispatch", "TerminateSignal"]
