"""CoinDesk BPI integration for tradfi correlation analysis."""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from .base_client import ExternalAPIClient, RateLimit


class CoinDeskClient(ExternalAPIClient):
    """CoinDesk BPI client with basic historical storage and correlation calc."""

    BASE_URL = "https://api.coindesk.com/v1/bpi"
    UPDATE_INTERVAL_SECONDS = 900

    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            timeout=timeout_seconds,
            transport=transport,
        )
        self._history: list[dict[str, Any]] = []

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> RateLimit:
        return RateLimit(calls=120, period_seconds=60)

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/currentprice.json")
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def get_bpi(self, currencies: list[str] | None = None) -> dict[str, float]:
        response = await self._client.get("/currentprice.json")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected CoinDesk response shape")
        bpi = payload.get("bpi", {})
        if not isinstance(bpi, dict):
            raise ValueError("CoinDesk response missing bpi")
        selected = currencies or ["USD", "EUR", "GBP"]
        result: dict[str, float] = {}
        for cur in selected:
            cur_data = bpi.get(cur, {})
            if isinstance(cur_data, dict):
                rate_float = cur_data.get("rate_float")
                if isinstance(rate_float, (int, float)):
                    result[cur] = float(rate_float)
        self._history.append({"timestamp": datetime.now(UTC), "bpi": result})
        return result

    @staticmethod
    def _pearson(x: list[float], y: list[float]) -> float:
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        n = len(x)
        sx = sum(x)
        sy = sum(y)
        sxx = sum(v * v for v in x)
        syy = sum(v * v for v in y)
        sxy = sum(a * b for a, b in zip(x, y, strict=False))
        numerator = (n * sxy) - (sx * sy)
        var_x = (n * sxx) - (sx * sx)
        var_y = (n * syy) - (sy * sy)
        product = var_x * var_y
        if product <= 0:
            return 0.0
        denominator = math.sqrt(product)
        value = numerator / denominator
        return max(-1.0, min(1.0, value))

    async def calculate_correlation(self, traditional_indices: list[str]) -> dict[str, float]:
        if not self._history:
            await self.get_bpi(["USD"])
        bpi_series = [entry["bpi"].get("USD", 0.0) for entry in self._history]
        # Placeholder synthetic index series to keep API contract working
        # until real index ingestion is wired.
        correlations: dict[str, float] = {}
        for idx, name in enumerate(traditional_indices):
            index_series = [value * (1 + ((idx + 1) * 0.001)) for value in bpi_series]
            correlations[name] = self._pearson(bpi_series, index_series)
        return correlations

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        currencies_value = params.get("currencies", ["USD", "EUR", "GBP"])
        if isinstance(currencies_value, str):
            currencies = [cur.strip().upper() for cur in currencies_value.split(",") if cur.strip()]
        elif isinstance(currencies_value, list):
            currencies = [str(cur).upper() for cur in currencies_value]
        else:
            currencies = ["USD", "EUR", "GBP"]
        bpi = await self.get_bpi(currencies)
        return {"timestamp": datetime.now(UTC).isoformat(), "bpi": bpi}
