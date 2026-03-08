"""CoinPaprika integration for market-cap/supply metrics."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.app.models.market import MarketMetrics

from .base_client import ExternalAPIClient, RateLimit


class CoinPaprikaClient(ExternalAPIClient):
    """CoinPaprika API client with local cache + staleness reporting."""

    BASE_URL = "https://api.coinpaprika.com/v1"
    UPDATE_INTERVAL_SECONDS = 300

    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
        now_fn: Callable[[], float] | None = None,
    ):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout_seconds,
            transport=transport,
        )
        self._cache: dict[str, MarketMetrics] = {}
        self._cached_at: dict[str, float] = {}
        self._now = now_fn or time.monotonic

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=120, period_seconds=60)

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/global")
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def get_market_metrics(self, coin_id: str) -> MarketMetrics:
        response = await self._client.get(f"/tickers/{coin_id}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected CoinPaprika response shape")
        quotes = payload.get("quotes", {})
        usd = quotes.get("USD", {}) if isinstance(quotes, dict) else {}
        metrics = MarketMetrics(
            coin_id=coin_id,
            volume_24h=float(usd.get("volume_24h", 0.0)),
            market_cap=float(usd.get("market_cap", 0.0)),
            circulating_supply=float(payload.get("circulating_supply", 0.0)),
            total_supply=(
                float(payload["total_supply"])
                if payload.get("total_supply") is not None
                else None
            ),
            max_supply=(
                float(payload["max_supply"])
                if payload.get("max_supply") is not None
                else None
            ),
            timestamp=datetime.now(UTC),
        )
        self._cache[coin_id] = metrics
        self._cached_at[coin_id] = self._now()
        return metrics

    def get_cached_metrics(
        self, coin_id: str, *, stale_after_seconds: float = 300.0
    ) -> dict[str, Any] | None:
        metrics = self._cache.get(coin_id)
        cached_at = self._cached_at.get(coin_id)
        if metrics is None or cached_at is None:
            return None
        age = self._now() - cached_at
        return {
            "metrics": metrics,
            "is_stale": age > stale_after_seconds,
            "age_seconds": age,
        }

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        coin_id = str(params.get("coin_id", "")).strip()
        if not coin_id:
            raise ValueError("coin_id is required")
        metrics = await self.get_market_metrics(coin_id)
        return {
            "coin_id": metrics.coin_id,
            "volume_24h": metrics.volume_24h,
            "market_cap": metrics.market_cap,
            "circulating_supply": metrics.circulating_supply,
            "total_supply": metrics.total_supply,
            "max_supply": metrics.max_supply,
            "timestamp": metrics.timestamp.isoformat(),
        }
