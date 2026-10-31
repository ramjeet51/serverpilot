import re

_ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_SECRET = re.compile(r"(spagent_[A-Za-z0-9_\-]+|(?:password|token|secret)\s*[:=]\s*\S+)", re.IGNORECASE)


def sanitize(line: str) -> str:
    cleaned = _SECRET.sub("[redacted]", _ANSI.sub("", line).replace("\r", "")).strip()
    return cleaned[:500]
