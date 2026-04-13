import os

from openai import OpenAI

_DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_DEFAULT_MODELS = ["openrouter/free"]


def get_models() -> list[str]:
    raw = os.environ.get("MODEL", "")
    if raw.strip():
        models = [m.strip() for m in raw.split(",") if m.strip()]
        if models:
            return models
    return _DEFAULT_MODELS.copy()


def _get_api_key() -> str:
    api_key = os.environ.get("API_KEY")
    if api_key:
        return api_key
    raise OSError("Missing API key.")


def _get_base_url() -> str:
    return os.environ.get("BASE_URL") or _DEFAULT_BASE_URL


def make_client() -> OpenAI:
    api_key = _get_api_key()
    return OpenAI(
        base_url=_get_base_url(),
        api_key=api_key,
    )
