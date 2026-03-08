"""On-chain metrics data source."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .base import AlternativeDataPoint, AlternativeDataSource


@dataclass(slots=True)
class OnChainMetricsSource(AlternativeDataSource):
    transaction_volume: float
    active_addresses: int
    network_fees: float
    whale_transfers: float
    miner_reserve_change: float

    def get_data(self, symbol: str) -> AlternativeDataPoint:
        observed_at = datetime.now(UTC)
        payload = {
            "transaction_volume": self.transaction_volume,
            "active_addresses": self.active_addresses,
            "network_fees": self.network_fees,
            "whale_transfers": self.whale_transfers,
            "miner_reserve_change": self.miner_reserve_change,
        }
        return AlternativeDataPoint(
            source="onchain_metrics",
            symbol=symbol,
            observed_at=observed_at,
            value=payload,
            quality_score=self.quality_score(payload),
            is_stale=self.is_stale(observed_at),
        )

    def normalize_data(self, payload: dict[str, float | int]) -> dict[str, float]:
        return {
            "transaction_volume": float(payload["transaction_volume"]),
            "active_addresses": float(payload["active_addresses"]),
            "network_fees": float(payload["network_fees"]),
            "whale_transfers": float(payload["whale_transfers"]),
            "miner_reserve_change": float(payload["miner_reserve_change"]),
        }
