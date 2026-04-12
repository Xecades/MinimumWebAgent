from ddgs import DDGS

from ..text import compact_whitespace

TOOL_DEF: dict = {
    "type": "function",
    "function": {
        "name": "search_web",
        "description": "Search the web using DuckDuckGo and return titles, snippets, and URLs.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5).",
                },
            },
            "required": ["query"],
        },
    },
}


def handle(query: str, max_results: int = 5, **kwargs: object) -> str:
    results = list(DDGS().text(query, max_results=max_results))
    if not results:
        return "No results found."
    lines = []
    for r in results:
        title = compact_whitespace(str(r["title"]))
        body = compact_whitespace(str(r["body"]))
        href = compact_whitespace(str(r["href"]))
        lines.append(f"Title: {title}\nSnippet: {body}\nURL: {href}\n")
    return "\n".join(lines)
