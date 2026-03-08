"""Pattern-driven strategy using the pattern detection subsystem."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from backend.app.models.market import MarketState, Side
from backend.app.models.portfolio import Portfolio
from backend.patterns.detector import PatternDetector
from backend.sim.engine import Order
from backend.strategies.base import Strategy


@dataclass(slots=True)
class PatternStrategyPerformance:
    trades: int = 0
    cumulative_pnl: float = 0.0
    wins: int = 0

    @property
    def win_rate(self) -> float:
        if self.trades <= 0:
            return 0.0
        return self.wins / self.trades


class PatternStrategy(Strategy):
    """Generates trade signals from high-confidence chart patterns."""

    name = "pattern"

    def __init__(
        self,
        *,
        detector: PatternDetector | None = None,
        min_confidence: float = 0.65,
        base_order_size: float = 100.0,
    ) -> None:
        self.detector = detector or PatternDetector()
        self.min_confidence = float(min_confidence)
        self.base_order_size = float(base_order_size)
        self.performance = PatternStrategyPerformance()

    def _to_frame(self, state: MarketState) -> pd.DataFrame:
        rows = [
            {
                "timestamp": candle.timestamp,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
            }
            for candle in state.candles
        ]
        return pd.DataFrame(rows)

    @staticmethod
    def _pattern_direction(pattern_type: str) -> int:
        bullish = {
            "double_bottom",
            "cup_and_handle",
            "bull_flag",
            "hammer",
            "bullish_engulfing",
            "morning_star",
            "ascending_triangle",
        }
        bearish = {
            "double_top",
            "head_and_shoulders",
            "bear_flag",
            "shooting_star",
            "bearish_engulfing",
            "evening_star",
            "descending_triangle",
        }
        if pattern_type in bullish:
            return 1
        if pattern_type in bearish:
            return -1
        return 0

    def on_bar(self, markets: dict[str, MarketState], portfolio: Portfolio) -> list[Order]:
        orders: list[Order] = []
        for market_id, state in markets.items():
            if len(state.candles) < 10 or state.orderbook is None:
                continue

            frame = self._to_frame(state)
            patterns = self.detector.detect_patterns(frame)
            if not patterns:
                continue

            def _confidence(item: dict[str, object]) -> float:
                pattern_obj = item.get("pattern")
                if hasattr(pattern_obj, "confidence"):
                    return float(getattr(pattern_obj, "confidence"))
                if isinstance(pattern_obj, dict):
                    return float(pattern_obj.get("confidence", 0.0))
                return 0.0

            top_pattern = max(
                patterns,
                key=_confidence,
            )
            pattern_obj = top_pattern.get("pattern")
            confidence = _confidence(top_pattern)
            if hasattr(pattern_obj, "pattern_type"):
                pattern_type = str(getattr(pattern_obj, "pattern_type"))
            elif isinstance(pattern_obj, dict):
                pattern_type = str(pattern_obj.get("pattern_type", "unknown"))
            else:
                pattern_type = "unknown"
            if confidence < self.min_confidence:
                continue

            direction = self._pattern_direction(pattern_type)
            current_pos = portfolio.positions.get(market_id)
            current_size = current_pos.size if current_pos else 0.0
            order_size = max(1.0, self.base_order_size * max(0.1, min(confidence, 1.0)))

            if direction > 0 and current_size <= 0:
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.BUY,
                        size=order_size,
                        strategy=self.name,
                        edge=confidence,
                    )
                )
            elif direction < 0 and current_size > 0:
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.SELL,
                        size=current_size,
                        strategy=self.name,
                        edge=confidence,
                    )
                )
        return orders

    def record_trade_outcome(self, pnl: float) -> None:
        self.performance.trades += 1
        self.performance.cumulative_pnl += float(pnl)
        if pnl > 0:
            self.performance.wins += 1
