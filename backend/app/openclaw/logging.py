"""Structured logging, correlation IDs, and secrets-safe log formatting."""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Any
from uuid import uuid4

_correlation_id: ContextVar[str | None] = ContextVar("openclaw_correlation_id", default=None)

_SECRET_PATTERNS = [
    re.compile(r"(api[_-]?key\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(token\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE),
    re.compile(r"(authorization\s*[=:]\s*)([^\s,;]+)", re.IGNORECASE),
]


def generate_correlation_id() -> str:
    return f"req-{uuid4().hex[:16]}"


def get_correlation_id() -> str | None:
    return _correlation_id.get()


@contextmanager
def correlation_context(correlation_id: str | None = None) -> Iterator[str]:
    active = correlation_id or generate_correlation_id()
    token = _correlation_id.set(active)
    try:
        yield active
    finally:
        _correlation_id.reset(token)


def mask_secrets(value: str) -> str:
    masked = value
    for pattern in _SECRET_PATTERNS:
        masked = pattern.sub(r"\1***", masked)
    return masked


class StructuredJsonFormatter(logging.Formatter):
    """JSON logging format with optional contextual data."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "message": mask_secrets(record.getMessage()),
        }
        correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        if correlation_id:
            payload["correlation_id"] = correlation_id
        context = getattr(record, "context", None)
        if isinstance(context, dict) and context:
            payload["context"] = context
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))


class StructuredLogger:
    """Thin logger facade enforcing consistent context schema."""

    def __init__(self, component: str):
        self._logger = logging.getLogger(component)

    def _emit(self, level: int, message: str, context: dict[str, Any] | None = None) -> None:
        context = context or {}
        self._logger.log(
            level,
            mask_secrets(message),
            extra={"context": context, "correlation_id": get_correlation_id()},
        )

    def debug(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._emit(logging.DEBUG, message, context)

    def info(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._emit(logging.INFO, message, context)

    def warning(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._emit(logging.WARNING, message, context)

    def error(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._emit(logging.ERROR, message, context)

    def exception(self, message: str, context: dict[str, Any] | None = None) -> None:
        self._logger.exception(
            mask_secrets(message),
            extra={"context": context or {}, "correlation_id": get_correlation_id()},
        )


def configure_structured_logging(
    *,
    level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> None:
    """Configure root logger for JSON output with console + optional file handler."""
    root = logging.getLogger()
    formatter = StructuredJsonFormatter()
    root.setLevel(level)

    if not root.handlers:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)
    else:
        for handler in root.handlers:
            handler.setFormatter(formatter)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        exists = any(
            isinstance(handler, TimedRotatingFileHandler)
            and getattr(handler, "baseFilename", "") == str(log_path)
            for handler in root.handlers
        )
        if not exists:
            rotating = TimedRotatingFileHandler(
                filename=str(log_path),
                when="midnight",
                backupCount=14,
                encoding="utf-8",
            )
            rotating.setFormatter(formatter)
            root.addHandler(rotating)
