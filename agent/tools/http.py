import asyncio
import re
from html.parser import HTMLParser

import httpx

_MAX_CHARS = 20_000


class _TextExtractor(HTMLParser):
    """Strip HTML tags and return visible text."""

    SKIP_TAGS = {"script", "style", "noscript", "head"}

    def __init__(self) -> None:
        super().__init__()
        self._skip = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP_TAGS:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP_TAGS and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        text = "\n".join(self._parts)
        # collapse multiple blank lines
        return re.sub(r"\n{3,}", "\n\n", text)


def _html_to_text(html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html)
        return p.get_text()
    except Exception:
        return html


TOOL_DEF: dict = {
    "type": "function",
    "function": {
        "name": "http_fetch",
        "description": (
            "Fetch one or more URLs in parallel and return each response status and body. "
            "Useful for REST APIs, raw HTML pages, or any HTTP resource."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "urls": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of URLs to fetch (fetched in parallel).",
                },
                "method": {
                    "type": "string",
                    "enum": ["GET", "POST", "PUT", "DELETE"],
                    "description": "HTTP method applied to all URLs (default: GET).",
                },
                "headers": {
                    "type": "object",
                    "description": "Optional HTTP headers applied to all requests.",
                },
                "body": {
                    "type": "string",
                    "description": "Request body for POST / PUT.",
                },
            },
            "required": ["urls"],
        },
    },
}


async def _fetch_one(
    client: httpx.AsyncClient,
    url: str,
    method: str,
    headers: dict,
    body: bytes | None,
) -> str:
    try:
        response = await client.request(method, url, headers=headers, content=body)
        content_type = response.headers.get("content-type", "")
        raw = response.text
        if "html" in content_type or raw.lstrip().startswith("<"):
            raw = _html_to_text(raw)
        text = raw[:_MAX_CHARS]
        return f"### {url}\nHTTP {response.status_code}\n\n{text}"
    except httpx.RequestError as exc:
        return f"### {url}\nRequest failed: {exc}"


async def _fetch_all(
    urls: list[str],
    method: str,
    headers: dict,
    body: bytes | None,
) -> list[str]:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as client:
        return await asyncio.gather(
            *[_fetch_one(client, url, method, headers, body) for url in urls]
        )


def handle(
    urls: list[str],
    method: str = "GET",
    headers: dict | None = None,
    body: str | None = None,
) -> str:
    results = asyncio.run(_fetch_all(urls, method, headers or {}, body.encode() if body else None))
    return "\n\n---\n\n".join(results)
