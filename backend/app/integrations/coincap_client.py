"""CoinCap secondary price feed client."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import httpx

from .base_client import ExternalAPIClient, RateLimit

logger = logging.getLogger(__name__)


class CoinCapClient(ExternalAPIClient):
    """CoinCap integration used as a secondary/fallback market data source."""

    BASE_URL = "https://api.coincap.io/v2"

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

    async def close(self) -> None:
        await self._client.aclose()

    def get_rate_limit(self) -> RateLimit:
        # CoinCap's public API limits are generally generous; keep a conservative client-side cap.
        return RateLimit(calls=200, period_seconds=60)

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/assets", params={"limit": 1})
            response.raise_for_status()
            payload = response.json()
            return isinstance(payload, dict) and "data" in payload
        except Exception:
            return False

    async def get_assets(self, ids: list[str]) -> list[dict[str, Any]]:
        response = await self._client.get("/assets", params={"ids": ",".join(ids)})
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected CoinCap response shape")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("CoinCap response missing 'data' list")
        return data

    @staticmethod
    def validate_price(
        *, primary_price: float, coincap_price: float, threshold: float = 0.05
    ) -> bool:
        if primary_price <= 0:
            raise ValueError("primary_price must be > 0")
        deviation = abs(coincap_price - primary_price) / primary_price
        if deviation > threshold:
            logger.warning(
                "price_anomaly_detected primary=%s coincap=%s deviation=%s threshold=%s",
                primary_price,
                coincap_price,
                deviation,
                threshold,
            )
            return False
        return True

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        ids_value = params.get("ids")
        if isinstance(ids_value, str):
            ids = [item.strip() for item in ids_value.split(",") if item.strip()]
        elif isinstance(ids_value, list):
            ids = [str(item) for item in ids_value]
        else:
            ids = []
        assets = await self.get_assets(ids)
        return {"data": assets}
