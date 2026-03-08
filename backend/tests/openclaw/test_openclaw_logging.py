from __future__ import annotations

import json
import logging
from io import StringIO

from backend.app.openclaw.logging import (
    StructuredJsonFormatter,
    correlation_context,
    generate_correlation_id,
    mask_secrets,
)


def test_mask_secrets_filters_tokens() -> None:
    value = "api_key=abc123 token:xyz"
    masked = mask_secrets(value)
    assert "abc123" not in masked
    assert "xyz" not in masked


def test_json_formatter_includes_correlation_id() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredJsonFormatter())
    logger = logging.getLogger("openclaw.test.logging")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    with correlation_context(generate_correlation_id()):
        logger.info("hello")

    payload = json.loads(stream.getvalue().strip())
    assert payload["message"] == "hello"
    assert payload["correlation_id"].startswith("req-")
