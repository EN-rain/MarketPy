"""Property tests for API gateway cache and fallback behavior.

Validates:
- Property 6: Cache TTL Expiration
- Property 7: Fallback Chain Activation
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.base_client import ExternalAPIClient, RateLimit
from backend.app.integrations.gateway import APIGateway


@dataclass
class MutableClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


class CountingClient(ExternalAPIClient):
    def __init__(self):
        self.calls = 0

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        self.calls += 1
        return {"calls": self.calls, "params": dict(params)}

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=10, period_seconds=60)

    async def health_check(self) -> bool:
        return True


class FlakyClient(ExternalAPIClient):
    def __init__(self, fail_times: int, label: str):
        self.fail_times = fail_times
        self.label = label
        self.calls = 0

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError(f"{self.label} failed")
        return {"source": self.label, "params": dict(params)}

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=10, period_seconds=60)

    async def health_check(self) -> bool:
        return True


# Property 6: Cache TTL Expiration
@given(
    ttl_seconds=st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False),
    first_advance=st.floats(min_value=0.0, max_value=9.0, allow_nan=False, allow_infinity=False),
    second_advance=st.floats(min_value=0.2, max_value=12.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_cache_ttl_expiration(
    ttl_seconds: float, first_advance: float, second_advance: float
) -> None:
    clock = MutableClock()
    gateway = APIGateway(default_ttl_seconds=ttl_seconds, now_fn=clock.now)
    client = CountingClient()
    gateway.register_client("coingecko", client)

    params = {"ids": "bitcoin"}
    first = await gateway.fetch_with_fallback("coingecko", params)
    clock.advance(min(first_advance, ttl_seconds * 0.9))
    second = await gateway.fetch_with_fallback("coingecko", params)

    # Within TTL, value must come from cache.
    assert first == second
    assert client.calls == 1

    clock.advance(max(second_advance, ttl_seconds + 0.1))
    third = await gateway.fetch_with_fallback("coingecko", params)

    # After TTL, a fresh fetch must happen.
    assert client.calls == 2
    assert third["calls"] == 2


# Property 7: Fallback Chain Activation
@given(
    primary_failures=st.integers(min_value=1, max_value=3),
    secondary_failures=st.integers(min_value=0, max_value=2),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_fallback_chain_activation(
    primary_failures: int, secondary_failures: int
) -> None:
    gateway = APIGateway(default_ttl_seconds=0)
    primary = FlakyClient(fail_times=primary_failures, label="coingecko")
    secondary = FlakyClient(fail_times=secondary_failures, label="binance")
    tertiary = FlakyClient(fail_times=0, label="coincap")

    gateway.register_client("coingecko", primary)
    gateway.register_client("binance", secondary)
    gateway.register_client("coincap", tertiary)
    gateway.register_fallback_chain("coingecko", ["binance", "coincap"])

    payload = await gateway.fetch_with_fallback("coingecko", {"ids": "bitcoin"})

    # Gateway must eventually return from first healthy provider in chain.
    assert payload["source"] in {"binance", "coincap"}
    assert primary.calls >= 1
