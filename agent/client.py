import os

from openai import OpenAI

MODEL = "stepfun/step-3.5-flash:free"


def make_client() -> OpenAI:
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise OSError("OPENROUTER_API_KEY environment variable is not set.")
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )
