"""Whale transfer tracking and alerting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class WhaleTransfer:
    wallet: str
    symbol: str
    usd_value: float
    direction: str
    timestamp: datetime


@dataclass(frozen=True, slots=True)
class WhaleAlert:
    symbol: str
    message: str
    level: str
    timestamp: datetime


class WhaleTracker:
    """Tracks large transfers and accumulation/distribution behavior."""

    def __init__(self, transfer_threshold_usd: float = 1_000_000.0) -> None:
        self.transfer_threshold_usd = float(transfer_threshold_usd)
        self._history: list[WhaleTransfer] = []

    def monitor_large_movements(self, transfers: list[WhaleTransfer]) -> list[WhaleTransfer]:
        flagged = [item for item in transfers if item.usd_value >= self.transfer_threshold_usd]
        self._history.extend(flagged)
        return flagged

    def accumulation_distribution(self, symbol: str) -> dict[str, float]:
        relevant = [item for item in self._history if item.symbol == symbol]
        if not relevant:
            return {"inflow_usd": 0.0, "outflow_usd": 0.0, "net_flow_usd": 0.0}
        inflow = sum(item.usd_value for item in relevant if item.direction.lower() in {"in", "buy", "deposit"})
        outflow = sum(item.usd_value for item in relevant if item.direction.lower() in {"out", "sell", "withdraw"})
        return {
            "inflow_usd": float(inflow),
            "outflow_usd": float(outflow),
            "net_flow_usd": float(inflow - outflow),
        }

    def generate_alerts(self, symbol: str) -> list[WhaleAlert]:
        flow = self.accumulation_distribution(symbol)
        alerts: list[WhaleAlert] = []
        now = datetime.now(UTC)
        if abs(flow["net_flow_usd"]) >= 5_000_000:
            trend = "accumulation" if flow["net_flow_usd"] > 0 else "distribution"
            alerts.append(
                WhaleAlert(
                    symbol=symbol,
                    message=f"Whale {trend} detected: net flow ${flow['net_flow_usd']:.0f}",
                    level="warning",
                    timestamp=now,
                )
            )
        large_moves = [item for item in self._history if item.symbol == symbol and item.usd_value >= 10_000_000]
        if large_moves:
            alerts.append(
                WhaleAlert(
                    symbol=symbol,
                    message=f"{len(large_moves)} mega-whale transfer(s) detected",
                    level="critical",
                    timestamp=now,
                )
            )
        return alerts
