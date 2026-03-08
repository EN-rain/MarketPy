"""Property tests for Discord webhook integration.

Validates:
- Property 9: Notification Retry with Backoff
- Property 10: Notification Message Completeness
- Property 11: Notification Queue Under Rate Limit
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.discord_client import (
    DiscordMessage,
    DiscordWebhookClient,
    RetryPolicy,
)


# Property 9: Notification Retry with Backoff
@given(failures_before_success=st.integers(min_value=1, max_value=2))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_notification_retry_with_backoff(failures_before_success: int) -> None:
    calls = {"count": 0}
    observed_delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        observed_delays.append(delay)

    async def handler(_: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] <= failures_before_success:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(204)

    client = DiscordWebhookClient(
        {"trades": "https://discord.example/webhook"},
        retry_policy=RetryPolicy(max_retries=3, base_delay_seconds=0.1, multiplier=2.0),
        sleep_fn=fake_sleep,
        transport=httpx.MockTransport(handler),
    )
    try:
        ok = await client.send_notification("trades", DiscordMessage(content="hello"))
    finally:
        await client.close()

    assert ok is True
    assert calls["count"] == failures_before_success + 1
    assert observed_delays == [0.1] if failures_before_success == 1 else [0.1, 0.2]


# Property 10: Notification Message Completeness
@given(
    trade_id=st.text(min_size=1, max_size=12),
    symbol=st.text(min_size=2, max_size=8),
    side=st.sampled_from(["buy", "sell"]),
    quantity=st.floats(
        min_value=0.0001, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    price=st.floats(
        min_value=0.0001, max_value=1_000_000, allow_nan=False, allow_infinity=False
    ),
    timestamp=st.text(min_size=10, max_size=32),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_notification_message_completeness(
    trade_id: str,
    symbol: str,
    side: str,
    quantity: float,
    price: float,
    timestamp: str,
) -> None:
    trade: dict[str, Any] = {
        "trade_id": trade_id,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "price": price,
        "timestamp": timestamp,
    }
    message = DiscordWebhookClient.format_trade_notification(trade)
    content = message.content
    assert trade_id in content
    assert symbol in content
    assert side.upper() in content
    assert str(price) in content
    assert timestamp in content


# Property 11: Notification Queue Under Rate Limit
@given(attempts=st.integers(min_value=1, max_value=30))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_notification_queue_under_rate_limit(attempts: int) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"message": "rate limited"})

    client = DiscordWebhookClient(
        {"alerts": "https://discord.example/webhook"},
        queue_max_size=200,
        transport=httpx.MockTransport(handler),
    )
    try:
        results = []
        for _ in range(attempts):
            ok = await client.send_notification(
                "alerts", DiscordMessage(content="rate-limited msg")
            )
            results.append(ok)
    finally:
        await client.close()

    assert all(result is True for result in results)
    assert client.queue_depth == attempts
