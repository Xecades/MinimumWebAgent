import os

from openai import OpenAI

# Fallback order: first available model is used; on rate-limit the next is tried.
MODELS: list[str] = [
    "minimax/minimax-m2.5:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "arcee-ai/trinity-large-preview:free",
]


def make_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OSError("OPENROUTER_API_KEY environment variable is not set.")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
