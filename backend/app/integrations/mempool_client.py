"""Mempool.space integration for Bitcoin on-chain metrics."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from typing import Any

import httpx

from backend.app.models.market import OnChainMetrics

from .base_client import ExternalAPIClient, RateLimit


class MempoolClient(ExternalAPIClient):
    """Client for mempool size, fee rates, and mining stats."""

    BASE_URL = "https://mempool.space/api/v1"
    UPDATE_INTERVAL_SECONDS = 60

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
        return RateLimit(calls=60, period_seconds=60)

    async def health_check(self) -> bool:
        try:
            response = await self._client.get("/fees/recommended")
            response.raise_for_status()
            return True
        except Exception:
            return False

    async def get_mempool_stats(self) -> dict[str, Any]:
        response = await self._client.get("/fees/mempool-blocks")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("Unexpected mempool stats response shape")
        total_vsize = sum(float(block.get("blockVSize", 0.0)) for block in payload)
        avg_fee = (
            sum(float(block.get("medianFee", 0.0)) for block in payload) / len(payload)
            if payload
            else 0.0
        )
        mempool_size_mb = total_vsize / 1_000_000
        return {
            "mempool_size_mb": mempool_size_mb,
            "fee_rate_sat_vb": avg_fee,
            "timestamp": datetime.now(UTC),
        }

    async def get_mining_stats(self) -> dict[str, Any]:
        response = await self._client.get("/mining/hashrate/3d")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Unexpected mining stats response shape")
        hashrates = payload.get("hashrates", [])
        difficulty = payload.get("difficulty", None)
        latest_hash_rate = (
            float(hashrates[-1]) if isinstance(hashrates, list) and hashrates else 0.0
        )
        return {"hash_rate_eh_s": latest_hash_rate, "difficulty": difficulty}

    async def get_onchain_metrics(self) -> OnChainMetrics:
        mempool = await self.get_mempool_stats()
        mining = await self.get_mining_stats()
        return OnChainMetrics(
            timestamp=mempool["timestamp"],
            mempool_size_mb=float(mempool["mempool_size_mb"]),
            fee_rate_sat_vb=float(mempool["fee_rate_sat_vb"]),
            hash_rate_eh_s=float(mining["hash_rate_eh_s"]),
            difficulty=float(mining["difficulty"]) if mining["difficulty"] is not None else None,
        )

    async def stream_updates(
        self, *, interval_seconds: float | None = None
    ) -> AsyncIterator[OnChainMetrics]:
        interval = interval_seconds or self.UPDATE_INTERVAL_SECONDS
        while True:
            yield await self.get_onchain_metrics()
            await asyncio.sleep(interval)

    async def fetch_data(self, params: Mapping[str, Any]) -> dict[str, Any]:
        metrics = await self.get_onchain_metrics()
        return {
            "timestamp": metrics.timestamp.isoformat(),
            "mempool_size_mb": metrics.mempool_size_mb,
            "fee_rate_sat_vb": metrics.fee_rate_sat_vb,
            "hash_rate_eh_s": metrics.hash_rate_eh_s,
            "difficulty": metrics.difficulty,
            "symbol": params.get("symbol", "BTC"),
        }
