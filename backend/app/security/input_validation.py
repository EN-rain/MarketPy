"""Input sanitization helpers for API models."""

from __future__ import annotations

import re


SAFE_TEXT_RE = re.compile(r"[^a-zA-Z0-9_\-:./, ]+")


def sanitize_text(value: str, *, max_length: int = 256) -> str:
    cleaned = SAFE_TEXT_RE.sub("", value).strip()
    return cleaned[:max_length]


def sanitize_symbol(value: str) -> str:
    cleaned = sanitize_text(value.upper(), max_length=24)
    return cleaned.replace("/", "").replace(" ", "")
