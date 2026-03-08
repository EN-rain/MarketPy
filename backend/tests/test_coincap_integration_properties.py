"""Tests for CoinCap secondary feed integration.

Validates:
- Property 8: Price anomaly detection logging (>5% divergence)
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.base_client import ExternalAPIClient, RateLimit
from backend.app.integrations.coincap_client import CoinCapClient
from backend.app.integrations.feed_failover import FeedFailoverManager
from backend.app.integrations.gateway import APIGateway


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.messages.append(record.getMessage())


# Property 8: Price Anomaly Detection
@given(
    primary_price=st.floats(
        min_value=1.0, max_value=1_000_000.0, allow_nan=False, allow_infinity=False
    ),
    divergence=st.floats(
        min_value=0.051, max_value=0.5, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.property_test
def test_property_price_anomaly_detection_logs_over_5_percent(
    primary_price: float, divergence: float
) -> None:
    coincap_price = primary_price * (1.0 + divergence)
    logger = logging.getLogger("backend.app.integrations.coincap_client")
    handler = _ListHandler()
    logger.addHandler(handler)
    logger.setLevel(logging.WARNING)
    try:
        ok = CoinCapClient.validate_price(primary_price=primary_price, coincap_price=coincap_price)
    finally:
        logger.removeHandler(handler)
    assert ok is False
    assert any("price_anomaly_detected" in msg for msg in handler.messages)


@dataclass
class MutableClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


class AlwaysFailClient(ExternalAPIClient):
    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        raise RuntimeError("primary down")

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=10, period_seconds=60)

    async def health_check(self) -> bool:
        return False


class SecondaryOkClient(ExternalAPIClient):
    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return {"source": "secondary", "params": dict(params)}

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=10, period_seconds=60)

    async def health_check(self) -> bool:
        return True


class RecoveringPrimaryClient(ExternalAPIClient):
    def __init__(self):
        self.healthy = False

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        if not self.healthy:
            raise RuntimeError("not healthy yet")
        return {"source": "primary", "params": dict(params)}

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=10, period_seconds=60)

    async def health_check(self) -> bool:
        return self.healthy


@pytest.mark.asyncio
async def test_secondary_switch_and_recovery_back_to_primary(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Task 10.2: switch to secondary on failure and recover back to primary."""

    clock = MutableClock()
    gateway = APIGateway(now_fn=clock.now)
    primary = RecoveringPrimaryClient()
    secondary = SecondaryOkClient()
    gateway.register_client("coingecko", primary)
    gateway.register_client("coincap", secondary)

    manager = FeedFailoverManager(
        gateway=gateway,
        primary_feed="coingecko",
        secondary_feed="coincap",
        recovery_window_seconds=30.0,
        now_fn=clock.now,
    )

    with caplog.at_level("INFO"):
        first = await manager.fetch({"ids": "bitcoin"})
        assert first["source"] == "secondary"
        assert manager.active_feed == "coincap"

        primary.healthy = True
        clock.advance(31.0)
        second = await manager.fetch({"ids": "bitcoin"})
        assert second["source"] == "primary"
        assert manager.active_feed == "coingecko"
        assert "feed_recovery" in caplog.text
