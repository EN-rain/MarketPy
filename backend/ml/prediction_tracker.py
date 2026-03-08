"""In-memory prediction tracking and lightweight online adaptation signals."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.app.models.config import settings


def _horizon_to_timedelta(horizon: str) -> timedelta:
    mapping = {
        "5m": timedelta(minutes=5),
        "15m": timedelta(minutes=15),
        "1h": timedelta(hours=1),
        "4h": timedelta(hours=4),
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
    confidence: float


class PredictionTracker:
    """Tracks predictions and resolves them when horizon elapses."""

    def __init__(self, storage_path: str | Path | None = None, snapshot_interval_seconds: int = 300) -> None:
        self.storage_path = Path(storage_path or (Path(settings.data_dir) / "prediction_tracking.json"))
        self.snapshot_interval_seconds = snapshot_interval_seconds
        self._pending: list[PendingPrediction] = []
        self._resolved: deque[dict[str, Any]] = deque(maxlen=1000)
        self._seen_keys: deque[str] = deque(maxlen=3000)
        self._seen_key_set: set[str] = set()
        self._latest_price_by_market: dict[str, float] = {}
        self._last_recorded_signal_at: dict[tuple[str, str], datetime] = {}
        self._load()

    @staticmethod
    def _ensure_utc(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    def _serialize(self) -> dict[str, Any]:
        return {
            "pending": [
                {
                    "market_id": item.market_id,
                    "horizon": item.horizon,
                    "signal_ts": item.signal_ts.isoformat(),
                    "due_ts": item.due_ts.isoformat(),
                    "base_price": item.base_price,
                    "predicted_price": item.predicted_price,
                    "confidence": item.confidence,
                }
                for item in self._pending
            ],
            "resolved": list(self._resolved),
            "latest_price_by_market": self._latest_price_by_market,
        }

    def _persist(self) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(self._serialize(), ensure_ascii=True), encoding="utf-8")
        except OSError:
            return

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            payload = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return

        pending_rows = payload.get("pending", [])
        resolved_rows = payload.get("resolved", [])
        latest_prices = payload.get("latest_price_by_market", {})

        self._pending = [
            PendingPrediction(
                market_id=str(row["market_id"]),
                horizon=str(row["horizon"]),
                signal_ts=self._ensure_utc(datetime.fromisoformat(str(row["signal_ts"]))),
                due_ts=self._ensure_utc(datetime.fromisoformat(str(row["due_ts"]))),
                base_price=float(row["base_price"]),
                predicted_price=float(row["predicted_price"]),
                confidence=float(row.get("confidence", 0.0)),
            )
            for row in pending_rows
            if isinstance(row, dict)
        ]
        self._resolved = deque(
            [row for row in resolved_rows if isinstance(row, dict)],
            maxlen=self._resolved.maxlen,
        )
        self._latest_price_by_market = {
            str(key): float(value) for key, value in latest_prices.items()
        }

    def record_signal(self, signal) -> None:
        """Record all horizon predictions from a signal."""
        signal_ts = self._ensure_utc(signal.timestamp)
        base_price = float(signal.current_mid)
        market_id = str(signal.market_id)

        for p in signal.predictions:
            horizon = p.horizon.value
            last_recorded = self._last_recorded_signal_at.get((market_id, horizon))
            if last_recorded and (signal_ts - last_recorded).total_seconds() < self.snapshot_interval_seconds:
                continue
            pred_price = float(p.predicted_price)
            key = f"{market_id}|{horizon}|{signal_ts.isoformat()}|{pred_price:.8f}"
            if key in self._seen_key_set:
                continue
            self._seen_keys.append(key)
            self._seen_key_set.add(key)
            self._last_recorded_signal_at[(market_id, horizon)] = signal_ts
            if len(self._seen_keys) >= self._seen_keys.maxlen:
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
                    confidence=float(getattr(p, "confidence", 0.0)),
                )
            )
        self._persist()

    def record_market_price(self, market_id: str, ts: datetime, price: float) -> None:
        """Resolve due predictions for market with latest price."""
        if price <= 0:
            return
        ts_utc = self._ensure_utc(ts)
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
                    "confidence": pending.confidence,
                    "win_rate": 1.0 if correct_direction else 0.0,
                }
            )
        self._pending = remaining
        self._persist()

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = list(self._resolved)[-limit:]
        rows.reverse()
        return rows

    def get_summary(self) -> dict[str, Any]:
        resolved = list(self._resolved)
        horizons = ["5m", "15m", "1h", "4h", "6h", "1d"]
        horizon_summary = {h: self._summarize_rows(h) for h in horizons}
        if not resolved:
            return {
                "resolved_predictions": 0,
                "pending_predictions": len(self._pending),
                "directional_accuracy": 0.0,
                "mean_error_pct": 0.0,
                "adaptive_kelly_multiplier": 1.0,
                "win_rate": 0.0,
                "by_horizon": horizon_summary,
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
            "win_rate": acc,
            "by_horizon": horizon_summary,
        }

    def _summarize_rows(self, horizon: str) -> dict[str, Any]:
        resolved = [row for row in self._resolved if row["horizon"] == horizon]
        pending = [row for row in self._pending if row.horizon == horizon]
        if not resolved:
            return {
                "resolved_predictions": 0,
                "pending_predictions": len(pending),
                "directional_accuracy": 0.0,
                "mean_error_pct": 0.0,
                "win_rate": 0.0,
            }
        directional_accuracy = sum(1 for row in resolved if row["correct_direction"]) / len(resolved)
        mean_error_pct = sum(row["error_pct"] for row in resolved) / len(resolved)
        return {
            "resolved_predictions": len(resolved),
            "pending_predictions": len(pending),
            "directional_accuracy": directional_accuracy,
            "mean_error_pct": mean_error_pct,
            "win_rate": directional_accuracy,
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
                    "confidence": p.confidence,
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

    def reset(self) -> None:
        self._pending = []
        self._resolved.clear()
        self._seen_keys.clear()
        self._seen_key_set.clear()
        self._latest_price_by_market.clear()
        self._last_recorded_signal_at.clear()
        self._persist()


_tracker = PredictionTracker()


def get_prediction_tracker() -> PredictionTracker:
    return _tracker
