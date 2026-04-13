from ftfy import fix_text


def repair_text(text: str) -> str:
    cleaned = text.replace("\ufeff", "").strip()
    return fix_text(cleaned)
