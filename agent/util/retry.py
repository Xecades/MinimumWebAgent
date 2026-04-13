import logging
import time

from openai import APIStatusError, NotFoundError, OpenAI, PermissionDeniedError, RateLimitError

from .backoff import compute_backoff_seconds
from .streaming import create_chat_completion_streamed


class RetryState:
    def __init__(self) -> None:
        self.model_idx = 0
        self.rate_limit_retries = 0


def request_with_retry(
    client: OpenAI,
    models: list[str],
    messages: list[dict],
    tools: list[dict],
    tool_choice: str,
    logger: logging.Logger,
    state: RetryState,
    max_rate_limit_retries_per_model: int,
) -> tuple[dict, str]:
    while True:
        current_model = models[state.model_idx]
        try:
            msg = create_chat_completion_streamed(
                client=client,
                model=current_model,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            state.rate_limit_retries = 0
            return msg, current_model
        except RateLimitError as err:
            _handle_rate_limit(
                err=err,
                current_model=current_model,
                models=models,
                logger=logger,
                state=state,
                max_rate_limit_retries_per_model=max_rate_limit_retries_per_model,
                label="Rate-limited",
            )
            continue
        except NotFoundError:
            if state.model_idx + 1 < len(models):
                state.model_idx += 1
                state.rate_limit_retries = 0
                logger.warning(
                    "Model unavailable on %s — falling back to %s",
                    current_model,
                    models[state.model_idx],
                )
                continue
            logger.error("All models exhausted (unavailable). Giving up.")
            raise
        except PermissionDeniedError as err:
            if _is_insufficient_quota(err) and state.model_idx + 1 < len(models):
                state.model_idx += 1
                state.rate_limit_retries = 0
                logger.warning(
                    "Quota exhausted on %s — falling back to %s",
                    current_model,
                    models[state.model_idx],
                )
                continue
            raise
        except APIStatusError as err:
            if err.status_code == 429:
                _handle_rate_limit(
                    err=err,
                    current_model=current_model,
                    models=models,
                    logger=logger,
                    state=state,
                    max_rate_limit_retries_per_model=max_rate_limit_retries_per_model,
                    label="429",
                )
                continue
            if err.status_code == 404 and state.model_idx + 1 < len(models):
                state.model_idx += 1
                state.rate_limit_retries = 0
                logger.warning(
                    "Model returned 404 on %s — falling back to %s",
                    current_model,
                    models[state.model_idx],
                )
                continue
            if err.status_code == 403 and _is_insufficient_quota(err):
                if state.model_idx + 1 < len(models):
                    state.model_idx += 1
                    state.rate_limit_retries = 0
                    logger.warning(
                        "Quota exhausted on %s — falling back to %s",
                        current_model,
                        models[state.model_idx],
                    )
                    continue
                logger.error("All models exhausted (insufficient quota). Giving up.")
                raise
            raise


def _handle_rate_limit(
    err: Exception,
    current_model: str,
    models: list[str],
    logger: logging.Logger,
    state: RetryState,
    max_rate_limit_retries_per_model: int,
    label: str,
) -> None:
    state.rate_limit_retries += 1
    if state.rate_limit_retries <= max_rate_limit_retries_per_model:
        sleep_s = compute_backoff_seconds(err, state.rate_limit_retries)
        logger.warning(
            "%s on %s (retry %s/%s) — backing off %.1fs",
            label,
            current_model,
            state.rate_limit_retries,
            max_rate_limit_retries_per_model,
            sleep_s,
        )
        time.sleep(sleep_s)
        return

    if state.model_idx + 1 < len(models):
        state.model_idx += 1
        state.rate_limit_retries = 0
        logger.warning(
            "%s on %s after retries — falling back to %s",
            label,
            current_model,
            models[state.model_idx],
        )
        return

    logger.error("All models exhausted (%s after retries). Giving up.", label.lower())
    raise err


def _is_insufficient_quota(err: Exception) -> bool:
    body = getattr(err, "body", None)
    if isinstance(body, dict):
        error = body.get("error", {})
        if isinstance(error, dict):
            code = str(error.get("code", "")).lower()
            msg = str(error.get("message", "")).lower()
            if "insufficient" in code and "quota" in code:
                return True
            if "quota" in msg or "额度不足" in msg:
                return True
    text = str(err).lower()
    return "insufficient_user_quota" in text or "quota" in text or "额度不足" in text
