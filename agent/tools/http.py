import httpx

# Cap response body to avoid flooding the context window.
_MAX_CHARS = 20_000

TOOL_DEF: dict = {
    "type": "function",
    "function": {
        "name": "http_fetch",
        "description": (
            "Fetch a URL and return the response status and body text. "
            "Useful for REST APIs, raw HTML pages, or any HTTP resource."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch.",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP method (default: GET).",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers as key-value pairs.",
                },
                "body": {
                    "type": "string",
                    "description": "Request body (for POST / PUT).",
                },
            },
            "required": ["url"],
        },
    },
}


def handle(
    url: str,
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
) -> str:
    try:
        with httpx.Client(follow_redirects=True, timeout=30) as client:
            response = client.request(
                method,
                url,
                headers=headers or {},
                content=body.encode() if body else None,
            )
        text = response.text[:_MAX_CHARS]
        return f"HTTP {response.status_code}\n\n{text}"
    except httpx.RequestError as exc:
        return f"Request failed: {exc}"
