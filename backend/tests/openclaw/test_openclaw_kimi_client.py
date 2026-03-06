from __future__ import annotations

import json

import pytest
from httpx import AsyncBaseTransport, Request, Response

from backend.app.openclaw.config import KimiK2Settings
from backend.app.openclaw.kimi_k2_client import KimiK2Client


class _RetryTransport(AsyncBaseTransport):
    def __init__(self) -> None:
        self.calls = 0

    async def handle_async_request(self, request: Request) -> Response:
        self.calls += 1
        if self.calls < 3:
            return Response(status_code=500, json={"error": "temporary"})
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "command_type": "price_check",
                                "symbol": "BTCUSDT",
                                "parameters": {},
                            }
                        )
                    }
                }
            ]
        }
        return Response(status_code=200, json=payload)


@pytest.mark.asyncio
async def test_kimi_client_retries_then_succeeds() -> None:
    transport = _RetryTransport()
    client = KimiK2Client(
        KimiK2Settings(
            api_key="test",
            rate_limit_per_minute=120,
            timeout_seconds=5,
            max_concurrent_calls=2,
        ),
        transport=transport,
    )
    intent = await client.extract_intent("check btc price", [])
    await client.close()
    assert transport.calls == 3
    assert intent["command_type"] == "price_check"
