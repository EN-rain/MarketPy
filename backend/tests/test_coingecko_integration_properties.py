"""Property tests for CoinGecko integration.

Validates:
- Property 4: API Response Time Compliance (<2s)
- Property 5: Rate Limit Compliance (<=50 calls/min)
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.coingecko_client import (
    CoinGeckoClient,
    CoinGeckoRateLimitExceededError,
)


@dataclass
class MutableClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


# Property 4: API Response Time Compliance
@given(
    simulated_delay=st.floats(
        min_value=0.0, max_value=1.8, allow_nan=False, allow_infinity=False
    )
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_coingecko_response_time_compliance(simulated_delay: float) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(simulated_delay)
        if request.url.path.endswith("/simple/price"):
            return httpx.Response(200, json={"bitcoin": {"usd": 50000}})
        return httpx.Response(404, json={"error": "not found"})

    transport = httpx.MockTransport(handler)
    client = CoinGeckoClient(transport=transport)
    start = time.perf_counter()
    try:
        payload = await client.get_price(["bitcoin"])
    finally:
        await client.close()
    elapsed = time.perf_counter() - start

    assert payload["bitcoin"]["usd"] == 50000
    assert elapsed < 2.0


# Property 5: Rate Limit Compliance
@given(request_count=st.integers(min_value=51, max_value=120))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_coingecko_rate_limit_compliance(request_count: int) -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/simple/price"):
            return httpx.Response(200, json={"bitcoin": {"usd": 50000}})
        return httpx.Response(404, json={"error": "not found"})

    clock = MutableClock()
    client = CoinGeckoClient(transport=httpx.MockTransport(handler), now_fn=clock.now)
    accepted = 0
    rejected = 0
    try:
        for _ in range(request_count):
            try:
                await client.get_price(["bitcoin"])
                accepted += 1
            except CoinGeckoRateLimitExceededError:
                rejected += 1
    finally:
        await client.close()

    assert accepted == 50
    assert rejected == request_count - 50


@pytest.mark.asyncio
async def test_coingecko_registered_fallback_chain_uses_binance() -> None:
    """Task 9.2: ensure gateway fallback chain can be configured CoinGecko -> Binance."""

    from backend.app.integrations.base_client import ExternalAPIClient, RateLimit
    from backend.app.integrations.gateway import APIGateway

    class AlwaysFail(ExternalAPIClient):
        async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
            raise RuntimeError("upstream unavailable")

        def get_rate_limit(self) -> RateLimit:
            return RateLimit(calls=50, period_seconds=60)

        async def health_check(self) -> bool:
            return False

    class BinanceOk(ExternalAPIClient):
        async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
            return {"source": "binance", "price": 50000.0}

        def get_rate_limit(self) -> RateLimit:
            return RateLimit(calls=1200, period_seconds=60)

        async def health_check(self) -> bool:
            return True

    gateway = APIGateway(default_ttl_seconds=10.0)
    gateway.register_client("coingecko", AlwaysFail())
    gateway.register_client("binance", BinanceOk())
    gateway.register_fallback_chain("coingecko", ["binance"])

    payload = await gateway.fetch_with_fallback("coingecko", {"ids": "bitcoin"})
    assert payload["source"] == "binance"
