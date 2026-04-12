import re
import subprocess

from ..util import compact_whitespace

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Each agent process sets its own session ID via set_session().
_session_id: str | None = None

# Cap output to avoid flooding the context window.
_MAX_CHARS = 20_000


def set_session(session_id: str) -> None:
    global _session_id
    _session_id = session_id


def _run(*args: str, timeout: int = 60) -> str:
    if _session_id is None:
        raise RuntimeError("Browser session not initialised — call set_session() first.")
    cmd = ["agent-browser", "--session", _session_id, *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    stdout = result.stdout.strip()
    stderr = result.stderr.strip()
    output = _ANSI_ESCAPE.sub("", stdout or stderr or "(no output)")
    output = compact_whitespace(output)
    return output[:_MAX_CHARS]


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOL_DEFS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "browser_open",
            "description": "Navigate the browser to a URL and wait for the page to load.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to open."},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_snapshot",
            "description": (
                "Capture the interactive elements on the current page. "
                "Returns element refs like @e1, @e2 that can be used in other browser tools."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element identified by its @ref from a previous snapshot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Element ref, e.g. @e3."},
                },
                "required": ["ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Clear an input field and type text into it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string", "description": "Element ref."},
                    "text": {"type": "string", "description": "Text to enter."},
                },
                "required": ["ref", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_text",
            "description": "Get the visible text of a page element, or the full page if no ref given.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "Element ref (optional — omit to get full page text).",
                    },
                },
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _open(url: str, **kwargs: object) -> str:
    out = _run("open", url)
    try:
        _run("wait", "--load", "networkidle", timeout=15)
    except subprocess.TimeoutExpired:
        pass  # page may still be usable even if not fully idle
    return out


def _snapshot(**kwargs: object) -> str:
    return _run("snapshot", "-i")


def _click(ref: str, **kwargs: object) -> str:
    return _run("click", ref)


def _fill(ref: str, text: str, **kwargs: object) -> str:
    return _run("fill", ref, text)


def _get_text(ref: str | None = None, **kwargs: object) -> str:
    return _run("get", "text", ref) if ref else _run("get", "text", "body")


HANDLERS: dict = {
    "browser_open": _open,
    "browser_snapshot": _snapshot,
    "browser_click": _click,
    "browser_fill": _fill,
    "browser_get_text": _get_text,
}
