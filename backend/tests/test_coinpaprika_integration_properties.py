"""Tests for CoinPaprika market metrics integration.

Validates:
- Property 12: API Response Field Completeness
- Property 13: Periodic Update Interval Compliance
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import pytest
from fastapi.testclient import TestClient
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.integrations.coinpaprika_client import CoinPaprikaClient
from backend.app.integrations.market_metrics_service import MarketMetricsService
from backend.app.main import AppConfig, create_app
from backend.app.models.market import MarketMetrics


@dataclass
class MutableClock:
    value: float = 0.0

    def now(self) -> float:
        return self.value

    def advance(self, delta: float) -> None:
        self.value += delta


# Property 12: API Response Field Completeness
@given(coin_id=st.from_regex(r"^[a-z0-9-]{3,20}$", fullmatch=True))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_coinpaprika_response_field_completeness(coin_id: str) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": coin_id,
                "circulating_supply": 19_000_000,
                "total_supply": 21_000_000,
                "max_supply": 21_000_000,
                "quotes": {"USD": {"volume_24h": 123456.78, "market_cap": 987654321.12}},
            },
        )

    client = CoinPaprikaClient(transport=httpx.MockTransport(handler))
    try:
        metrics = await client.get_market_metrics(coin_id)
    finally:
        await client.close()

    assert metrics.coin_id == coin_id
    assert metrics.volume_24h >= 0
    assert metrics.market_cap >= 0
    assert metrics.circulating_supply >= 0
    assert metrics.timestamp is not None


# Property 13: Periodic Update Interval Compliance
@given(
    under_interval=st.floats(
        min_value=0.0, max_value=299.0, allow_nan=False, allow_infinity=False
    ),
    over_interval=st.floats(
        min_value=300.0, max_value=600.0, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_periodic_update_interval_compliance(
    under_interval: float, over_interval: float
) -> None:
    class FakeCoinPaprika:
        def __init__(self):
            self.calls = 0

        async def get_market_metrics(self, coin_id: str) -> MarketMetrics:
            self.calls += 1
            return MarketMetrics(
                coin_id=coin_id,
                volume_24h=1.0,
                market_cap=2.0,
                circulating_supply=3.0,
                total_supply=4.0,
                max_supply=5.0,
                timestamp=datetime.now(UTC),
            )

        def get_cached_metrics(self, coin_id: str, *, stale_after_seconds: float = 300.0):
            return {
                "metrics": MarketMetrics(
                    coin_id=coin_id,
                    volume_24h=1.0,
                    market_cap=2.0,
                    circulating_supply=3.0,
                    total_supply=4.0,
                    max_supply=5.0,
                    timestamp=datetime.now(UTC),
                ),
                "is_stale": False,
                "age_seconds": 0.0,
            }

    clock = MutableClock()
    service = MarketMetricsService(
        client=FakeCoinPaprika(),  # type: ignore[arg-type]
        tracked_coin_ids=["btc-bitcoin"],
        update_interval_seconds=300.0,
        now_fn=clock.now,
    )

    await service.update_due_coins()
    assert service.client.calls == 1  # type: ignore[attr-defined]

    clock.advance(under_interval)
    await service.update_due_coins()
    assert service.client.calls == 1  # type: ignore[attr-defined]

    clock.advance(over_interval)
    await service.update_due_coins()
    assert service.client.calls == 2  # type: ignore[attr-defined]


def test_market_metrics_endpoint_returns_staleness_indicator() -> None:
    app = create_app(AppConfig(enable_binance_stream=False, enable_coinpaprika_metrics=False))

    class StubService:
        @staticmethod
        def get_metrics(coin_id: str):
            return {
                "metrics": MarketMetrics(
                    coin_id=coin_id,
                    volume_24h=111.0,
                    market_cap=222.0,
                    circulating_supply=333.0,
                    total_supply=444.0,
                    max_supply=555.0,
                    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                ),
                "is_stale": True,
                "age_seconds": 601.0,
            }

        @staticmethod
        async def update_coin(coin_id: str) -> bool:
            return coin_id == "btc-bitcoin"

    app.state.market_metrics_service = StubService()
    with TestClient(app) as client:
        resp = client.get("/api/metrics/market/btc-bitcoin")
        assert resp.status_code == 200
        data = resp.json()
        assert data["coin_id"] == "btc-bitcoin"
        assert "volume_24h" in data
        assert "market_cap" in data
        assert "circulating_supply" in data
        assert "timestamp" in data
        assert data["is_stale"] is True
