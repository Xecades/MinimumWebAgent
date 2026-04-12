import time

_BASE_BACKOFF_SECONDS = 1.5
_MAX_BACKOFF_SECONDS = 60.0


def compute_backoff_seconds(err: Exception, attempt: int) -> float:
    retry_after = _extract_retry_after_seconds(err)
    if retry_after is not None:
        return min(max(retry_after, _BASE_BACKOFF_SECONDS), _MAX_BACKOFF_SECONDS)
    exp = _BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
    return min(exp, _MAX_BACKOFF_SECONDS)


def _extract_retry_after_seconds(err: Exception) -> float | None:
    headers: dict[str, str] = {}
    response = getattr(err, "response", None)
    if response is not None:
        raw_headers = getattr(response, "headers", None)
        if raw_headers is not None:
            headers.update({str(k).lower(): str(v) for k, v in dict(raw_headers).items()})

    body = getattr(err, "body", None)
    if isinstance(body, dict):
        metadata = body.get("error", {}).get("metadata", {})
        meta_headers = metadata.get("headers", {})
        if isinstance(meta_headers, dict):
            headers.update({str(k).lower(): str(v) for k, v in meta_headers.items()})

    retry_after = headers.get("retry-after")
    if retry_after is not None:
        try:
            return float(retry_after)
        except ValueError:
            pass

    reset = headers.get("x-ratelimit-reset")
    if reset is None:
        return None

    try:
        reset_num = float(reset)
    except ValueError:
        return None

    now = time.time()
    reset_ts = reset_num / 1000.0 if reset_num > 10_000_000_000 else reset_num
    delay = reset_ts - now
    return delay if delay > 0 else None
