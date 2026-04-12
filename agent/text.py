import re

_MULTI_SPACE_RE = re.compile(r"[ \t\f\v\u00a0]+")
_AROUND_NEWLINE_SPACE_RE = re.compile(r" *\n *")
_MULTI_NEWLINE_RE = re.compile(r"\n{2,}")


def compact_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTI_SPACE_RE.sub(" ", text)
    text = _AROUND_NEWLINE_SPACE_RE.sub("\n", text)
    text = _MULTI_NEWLINE_RE.sub("\n", text)
    return text.strip()
