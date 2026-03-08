"""Integration tests for storage wiring in integration services."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
import pytest

from backend.app.integrations.hackernews_client import HackerNewsClient
from backend.app.integrations.market_metrics_service import MarketMetricsService
from backend.app.integrations.onchain_monitor import OnChainMonitor
from backend.app.models.market import MarketMetrics, OnChainMetrics
from backend.app.storage.metrics_store import MetricsStore


@pytest.mark.asyncio
async def test_market_metrics_service_persists_rows(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))

    class FakeCoinPaprika:
        async def get_market_metrics(self, coin_id: str) -> MarketMetrics:
            return MarketMetrics(
                coin_id=coin_id,
                volume_24h=10.0,
                market_cap=20.0,
                circulating_supply=30.0,
                total_supply=40.0,
                max_supply=50.0,
                timestamp=datetime.now(UTC),
            )

        def get_cached_metrics(self, coin_id: str, *, stale_after_seconds: float = 300.0):
            return None

    service = MarketMetricsService(
        client=FakeCoinPaprika(),  # type: ignore[arg-type]
        tracked_coin_ids=["btc-bitcoin"],
        store=store,
    )
    try:
        ok = await service.update_coin("btc-bitcoin")
        assert ok is True
        assert store.count_rows("market_metrics") == 1
    finally:
        store.close()


def test_onchain_monitor_persists_rows(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))
    monitor = OnChainMonitor(store=store)
    try:
        monitor.record(
            OnChainMetrics(
                timestamp=datetime.now(UTC),
                mempool_size_mb=120.0,
                fee_rate_sat_vb=150.0,
                hash_rate_eh_s=200.0,
                difficulty=1.0,
            )
        )
        assert store.count_rows("onchain_metrics") == 1
    finally:
        store.close()


@pytest.mark.asyncio
async def test_hackernews_client_persists_sentiment_rows(tmp_path):
    store = MetricsStore(str(tmp_path / "metrics.db"))

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/topstories.json"):
            return httpx.Response(200, json=[1])
        if request.url.path.endswith("/item/1.json"):
            return httpx.Response(200, json={"title": "bullish breakout for bitcoin"})
        return httpx.Response(200, json={})

    client = HackerNewsClient(transport=httpx.MockTransport(handler), store=store)
    try:
        await client.fetch_data({"keywords": ["bitcoin"]})
        assert store.count_rows("sentiment_scores") == 1
    finally:
        await client.close()
        store.close()

