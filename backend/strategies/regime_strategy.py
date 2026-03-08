"""Regime-adaptive strategy implementation."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.app.models.market import MarketState, Side
from backend.app.models.portfolio import Portfolio
from backend.regime.classifier import RegimeClassifier
from backend.regime.parameters import RegimeParameterManager
from backend.sim.engine import Order
from backend.strategies.base import Strategy


@dataclass(slots=True)
class RegimePerformance:
    by_regime: dict[str, list[float]] = field(default_factory=dict)

    def record(self, regime: str, pnl: float) -> None:
        self.by_regime.setdefault(regime, []).append(float(pnl))

    def summary(self) -> dict[str, float]:
        out: dict[str, float] = {}
        for regime, values in self.by_regime.items():
            out[regime] = sum(values) / len(values) if values else 0.0
        return out


class RegimeAdaptiveStrategy(Strategy):
    """Switches behavior and sizing according to the detected market regime."""

    name = "regime_adaptive"

    def __init__(
        self,
        *,
        classifier: RegimeClassifier | None = None,
        parameter_manager: RegimeParameterManager | None = None,
        base_order_size: float = 100.0,
        momentum_threshold: float = 0.001,
    ) -> None:
        self.classifier = classifier or RegimeClassifier()
        self.parameter_manager = parameter_manager or RegimeParameterManager()
        self.base_order_size = float(base_order_size)
        self.momentum_threshold = float(momentum_threshold)
        self.performance = RegimePerformance()
        self.last_regime: dict[str, str] = {}

    @staticmethod
    def _frame_from_state(state: MarketState) -> pd.DataFrame:
        return pd.DataFrame(
            [{"close": candle.close, "volume": candle.volume, "timestamp": candle.timestamp} for candle in state.candles]
        )

    def _regime_signal(self, regime: str, momentum: float) -> int:
        if regime == "trending_up" and momentum > self.momentum_threshold:
            return 1
        if regime == "trending_down" and momentum < -self.momentum_threshold:
            return -1
        if regime in {"crisis", "high_volatility"} and momentum < 0:
            return -1
        if regime == "ranging" and abs(momentum) < self.momentum_threshold:
            return 0
        return 0

    def on_bar(self, markets: dict[str, MarketState], portfolio: Portfolio) -> list[Order]:
        orders: list[Order] = []
        for market_id, state in markets.items():
            if len(state.candles) < 30 or state.orderbook is None:
                continue
            frame = self._frame_from_state(state)
            classification = self.classifier.classify_from_frame(frame)
            self.last_regime[market_id] = classification.regime

            close_now = float(state.candles[-1].close)
            close_prev = float(state.candles[-2].close)
            momentum = (close_now / max(close_prev, 1e-9)) - 1.0
            signal = self._regime_signal(classification.regime, momentum)

            adjusted = self.parameter_manager.adjust(
                classification.regime,
                profit_target=1.0,
                stop_loss=1.0,
                position_size=self.base_order_size,
            )
            size = max(1.0, adjusted["position_size"] * max(0.2, classification.confidence))

            current_pos = portfolio.positions.get(market_id)
            current_size = current_pos.size if current_pos else 0.0
            if signal > 0 and current_size <= 0:
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.BUY,
                        size=size,
                        strategy=self.name,
                        edge=classification.confidence,
                    )
                )
            elif signal < 0 and current_size > 0:
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.SELL,
                        size=current_size,
                        strategy=self.name,
                        edge=classification.confidence,
                    )
                )
        return orders

    def record_trade_outcome(self, market_id: str, pnl: float) -> None:
        regime = self.last_regime.get(market_id, "unknown")
        self.performance.record(regime, pnl)
