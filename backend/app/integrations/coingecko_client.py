"""CoinGecko API integration client."""

from __future__ import annotations

import time
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from .base_client import ExternalAPIClient, RateLimit


class CoinGeckoRateLimitExceededError(RuntimeError):
    """Raised when client-side CoinGecko rate limit is exceeded."""


class CoinGeckoClient(ExternalAPIClient):
    """CoinGecko client with rate limiting and typed helpers."""

    BASE_URL = "https://api.coingecko.com/api/v3"

    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        rate_limit_per_minute: int = 50,
        transport: httpx.AsyncBaseTransport | None = None,
        now_fn: Callable[[], float] | None = None,
    ):
        self._timeout_seconds = timeout_seconds
        self._rate_limit_per_minute = rate_limit_per_minute
        self._now = now_fn or time.monotonic
        self._request_times: deque[float] = deque()
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=self._timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=self._rate_limit_per_minute, period_seconds=60)

    def _enforce_rate_limit(self) -> None:
        now = self._now()
        while self._request_times and now - self._request_times[0] >= 60:
            self._request_times.popleft()
        if len(self._request_times) >= self._rate_limit_per_minute:
            raise CoinGeckoRateLimitExceededError(
                f"CoinGecko rate limit exceeded ({self._rate_limit_per_minute} calls/minute)"
            )
        self._request_times.append(now)

    async def _get(
        self, path: str, params: Mapping[str, Any]
    ) -> dict[str, Any] | list[dict[str, Any]]:
        self._enforce_rate_limit()
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        try:
            data = await self._get("/ping", {})
            return isinstance(data, dict) and data.get("gecko_says") is not None
        except Exception:
            return False

    async def get_price(
        self,
        coin_ids: list[str],
        *,
        vs_currencies: list[str] | None = None,
    ) -> dict[str, dict[str, float]]:
        if not coin_ids:
            return {}
        currencies = vs_currencies or ["usd"]
        payload = await self._get(
            "/simple/price",
            {
                "ids": ",".join(coin_ids),
                "vs_currencies": ",".join(currencies),
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("Unexpected CoinGecko price response shape")
        return payload

    async def get_market_data(self, coin_id: str) -> dict[str, Any]:
        payload = await self._get(
            "/coins/markets",
            {
                "vs_currency": "usd",
                "ids": coin_id,
            },
        )
        if not isinstance(payload, list):
            raise ValueError("Unexpected CoinGecko market response shape")
        return payload[0] if payload else {}

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        coin_ids_value = params.get("coin_ids") or params.get("ids")
        if isinstance(coin_ids_value, str):
            coin_ids = [item.strip() for item in coin_ids_value.split(",") if item.strip()]
        elif isinstance(coin_ids_value, list):
            coin_ids = [str(item) for item in coin_ids_value]
        else:
            coin_ids = []

        vs_currencies_value = params.get("vs_currencies")
        if isinstance(vs_currencies_value, str):
            vs_currencies = [
                item.strip() for item in vs_currencies_value.split(",") if item.strip()
            ]
        elif isinstance(vs_currencies_value, list):
            vs_currencies = [str(item) for item in vs_currencies_value]
        else:
            vs_currencies = ["usd"]

        return await self.get_price(coin_ids, vs_currencies=vs_currencies)
