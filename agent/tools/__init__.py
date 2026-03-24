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
        return browser.HANDLERS[name](**args)
    match name:
        case "http_fetch":
            return http.handle(**args)
        case "search_web":
            return search.handle(**args)
        case "terminate":
            return terminate.handle(**args)  # may raise TerminateSignal
        case _:
            return f"Unknown tool: {name!r}"


__all__ = ["ALL_TOOLS", "dispatch", "TerminateSignal"]
