"""In-memory prediction tracking and lightweight online adaptation signals."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any


def _horizon_to_timedelta(horizon: str) -> timedelta:
    mapping = {
        "1h": timedelta(hours=1),
        "6h": timedelta(hours=6),
        "1d": timedelta(days=1),
    }
    return mapping.get(horizon, timedelta(hours=1))


@dataclass
class PendingPrediction:
    market_id: str
    horizon: str
    signal_ts: datetime
    due_ts: datetime
    base_price: float
    predicted_price: float


class PredictionTracker:
    """Tracks predictions and resolves them when horizon elapses."""

    def __init__(self) -> None:
        self._pending: list[PendingPrediction] = []
        self._resolved: deque[dict[str, Any]] = deque(maxlen=1000)
        self._seen_keys: deque[str] = deque(maxlen=3000)
        self._seen_key_set: set[str] = set()
        self._latest_price_by_market: dict[str, float] = {}

    def record_signal(self, signal) -> None:
        """Record all horizon predictions from a signal."""
        signal_ts = signal.timestamp if signal.timestamp.tzinfo else signal.timestamp.replace(tzinfo=UTC)
        base_price = float(signal.current_mid)
        market_id = str(signal.market_id)

        for p in signal.predictions:
            horizon = p.horizon.value
            pred_price = float(p.predicted_price)
            key = f"{market_id}|{horizon}|{signal_ts.isoformat()}|{pred_price:.8f}"
            if key in self._seen_key_set:
                continue
            self._seen_keys.append(key)
            self._seen_key_set.add(key)
            if len(self._seen_keys) == self._seen_keys.maxlen:
                while len(self._seen_keys) > int(self._seen_keys.maxlen * 0.9):
                    old = self._seen_keys.popleft()
                    self._seen_key_set.discard(old)

            self._pending.append(
                PendingPrediction(
                    market_id=market_id,
                    horizon=horizon,
                    signal_ts=signal_ts,
                    due_ts=signal_ts + _horizon_to_timedelta(horizon),
                    base_price=base_price,
                    predicted_price=pred_price,
                )
            )

    def record_market_price(self, market_id: str, ts: datetime, price: float) -> None:
        """Resolve due predictions for market with latest price."""
        if price <= 0:
            return
        ts_utc = ts if ts.tzinfo else ts.replace(tzinfo=UTC)
        self._latest_price_by_market[market_id] = float(price)

        remaining: list[PendingPrediction] = []
        for pending in self._pending:
            if pending.market_id != market_id or pending.due_ts > ts_utc:
                remaining.append(pending)
                continue

            actual_price = float(price)
            pred_change = pending.predicted_price - pending.base_price
            actual_change = actual_price - pending.base_price
            predicted_direction = 1 if pred_change > 0 else (-1 if pred_change < 0 else 0)
            actual_direction = 1 if actual_change > 0 else (-1 if actual_change < 0 else 0)
            correct_direction = predicted_direction == actual_direction
            abs_error = abs(pending.predicted_price - actual_price)
            error_pct = abs_error / pending.base_price if pending.base_price > 0 else 0.0

            self._resolved.append(
                {
                    "market_id": pending.market_id,
                    "horizon": pending.horizon,
                    "signal_ts": pending.signal_ts.isoformat(),
                    "resolved_ts": ts_utc.isoformat(),
                    "base_price": pending.base_price,
                    "predicted_price": pending.predicted_price,
                    "actual_price": actual_price,
                    "abs_error": abs_error,
                    "error_pct": error_pct,
                    "predicted_direction": predicted_direction,
                    "actual_direction": actual_direction,
                    "correct_direction": correct_direction,
                }
            )
        self._pending = remaining

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = list(self._resolved)[-limit:]
        rows.reverse()
        return rows

    def get_summary(self) -> dict[str, Any]:
        resolved = list(self._resolved)
        if not resolved:
            return {
                "resolved_predictions": 0,
                "pending_predictions": len(self._pending),
                "directional_accuracy": 0.0,
                "mean_error_pct": 0.0,
                "adaptive_kelly_multiplier": 1.0,
            }
        acc = sum(1 for r in resolved if r["correct_direction"]) / len(resolved)
        mean_error = sum(r["error_pct"] for r in resolved) / len(resolved)
        # Adaptive multiplier: reward accuracy > 55%, penalize below.
        multiplier = max(0.5, min(1.5, 1.0 + (acc - 0.55) * 2.0))
        return {
            "resolved_predictions": len(resolved),
            "pending_predictions": len(self._pending),
            "directional_accuracy": acc,
            "mean_error_pct": mean_error,
            "adaptive_kelly_multiplier": multiplier,
        }

    def get_live_preview(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return pending predictions with provisional error vs latest market price."""
        rows = self._pending[-limit:]
        out: list[dict[str, Any]] = []
        for p in reversed(rows):
            current = self._latest_price_by_market.get(p.market_id)
            if current is None:
                continue
            out.append(
                {
                    "market_id": p.market_id,
                    "horizon": p.horizon,
                    "signal_ts": p.signal_ts.isoformat(),
                    "due_ts": p.due_ts.isoformat(),
                    "base_price": p.base_price,
                    "predicted_price": p.predicted_price,
                    "current_price": current,
                    "provisional_error": p.predicted_price - current,
                    "provisional_error_pct": (p.predicted_price - current) / p.base_price
                    if p.base_price > 0
                    else 0.0,
                }
            )
        return out

    def get_chart_points(
        self,
        market_id: str | None = None,
        horizon: str | None = None,
        limit: int = 120,
    ) -> list[dict[str, Any]]:
        rows = list(self._resolved)
        if market_id:
            rows = [r for r in rows if r["market_id"] == market_id]
        if horizon:
            rows = [r for r in rows if r["horizon"] == horizon]
        rows = rows[-limit:]
        return [
            {
                "t": r["resolved_ts"],
                "predicted": r["predicted_price"],
                "actual": r["actual_price"],
                "market_id": r["market_id"],
                "horizon": r["horizon"],
            }
            for r in rows
        ]


_tracker = PredictionTracker()


def get_prediction_tracker() -> PredictionTracker:
    return _tracker
