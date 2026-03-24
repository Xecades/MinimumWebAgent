import asyncio

import httpx

_MAX_CHARS = 20_000

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
        text = response.text[:_MAX_CHARS]
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
