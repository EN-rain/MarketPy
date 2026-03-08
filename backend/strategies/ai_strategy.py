"""AI-driven trading strategy using trained XGBoost models.

Computes predictions for all horizons, checks edge vs costs,
and uses fractional Kelly sizing for position decisions.
"""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime

from backend.app.models.market import MarketState, Side
from backend.app.models.portfolio import Portfolio
from backend.app.models.signal import EdgeDecision, Signal
from backend.ml.inference import Inferencer
from backend.ml.prediction_tracker import get_prediction_tracker
from backend.sim.engine import Order
from backend.sim.fees import estimate_breakeven_edge
from backend.strategies.base import Strategy

logger = logging.getLogger(__name__)


class AIStrategy(Strategy):
    """AI strategy using XGBoost price predictions.

    Decision logic:
        1. Compute predicted price at each horizon
        2. Pick the horizon with the best edge
        3. Check if edge > costs (spread + fees + buffer)
        4. Size using fractional Kelly criterion
        5. Trade only if all checks pass

    Args:
        inferencer: Loaded Inferencer with trained models.
        edge_buffer: Minimum edge over breakeven to trade.
        kelly_fraction: Fraction of Kelly criterion estimate to use.
        order_size: Default order size (used when Kelly gives 0).
    """

    name = "ai"

    def __init__(
        self,
        inferencer: Inferencer | None = None,
        edge_buffer: float = 0.02,
        kelly_fraction: float = 0.1,
        order_size: float = 100.0,
    ) -> None:
        self.inferencer = inferencer or Inferencer()
        self.edge_buffer = edge_buffer
        self.kelly_fraction = kelly_fraction
        self.order_size = order_size
        self.last_signals: dict[str, Signal] = {}
        self._insufficient_history_warned: set[str] = set()
        self.prediction_tracker = get_prediction_tracker()

    def _compute_features(self, state: MarketState) -> dict[str, float]:
        """Extract features from market state for inference."""
        candles = state.candles
        features: dict[str, float] = {}

        if len(candles) < 60:
            market_id = state.info.condition_id
            if market_id not in self._insufficient_history_warned:
                self._insufficient_history_warned.add(market_id)
                logger.info(
                    "AI strategy waiting for minimum history: market=%s have=%s need=60",
                    market_id,
                    len(candles),
                )
            return features

        prices = [c.mid for c in candles]
        current = prices[-1]

        # Lag returns
        for lag in [1, 5, 15, 60]:
            if len(prices) > lag:
                past = prices[-lag - 1]
                features[f"ret_{lag}"] = math.log(current / past) if past > 0 else 0.0

        # Rolling volatility
        for window in [12, 48]:
            if len(prices) > window:
                returns = [
                    math.log(prices[i] / prices[i - 1])
                    for i in range(len(prices) - window, len(prices))
                    if prices[i - 1] > 0
                ]
                if returns:
                    mean_r = sum(returns) / len(returns)
                    var = sum((r - mean_r) ** 2 for r in returns) / len(returns)
                    features[f"vol_{window}"] = math.sqrt(var)

        # Spread features
        if state.orderbook and state.orderbook.spread is not None:
            features["spread_pct"] = state.orderbook.spread / current if current > 0 else 0
            spreads = [c.spread for c in candles[-12:]]
            features["spread_avg_12"] = sum(spreads) / len(spreads) if spreads else 0

        # Time features
        if candles:
            ts = candles[-1].timestamp
            features["hour_of_day"] = float(ts.hour)
            features["day_of_week"] = float(ts.weekday())

        if state.time_to_close is not None:
            features["time_to_close"] = state.time_to_close

        return features

    def _kelly_size(self, edge: float, price: float, portfolio: Portfolio) -> float:
        """Compute position size using fractional Kelly criterion.

        f* = (p*b - q) / b  where p=win prob, b=odds, q=1-p
        Simplified: f* ≈ edge / variance (for small edge)
        """
        if edge <= 0 or price <= 0:
            return 0.0

        # Lightweight online adaptation from recent prediction quality.
        adaptive = self.prediction_tracker.get_summary().get("adaptive_kelly_multiplier", 1.0)
        # Simplified Kelly: edge / assumed volatility
        assumed_vol = 0.05  # conservative
        kelly_full = edge / (assumed_vol**2)
        kelly_fraction = kelly_full * self.kelly_fraction * adaptive

        # Cap at reasonable fraction of equity
        max_size = portfolio.total_equity * 0.1
        size = min(kelly_fraction * portfolio.total_equity, max_size)

        return max(0.0, size)

    def on_bar(
        self,
        markets: dict[str, MarketState],
        portfolio: Portfolio,
    ) -> list[Order]:
        orders: list[Order] = []

        for market_id, state in markets.items():
            if not state.orderbook or state.orderbook.mid is None:
                continue

            ob = state.orderbook
            mid = ob.mid
            bid = ob.best_bid or mid
            ask = ob.best_ask or mid
            spread = ob.spread or 0.0

            # Compute features
            features = self._compute_features(state)
            if not features:
                continue

            # Get predictions
            predictions = self.inferencer.predict(features, current_mid=mid)
            if not predictions:
                continue

            # Find best edge across horizons
            best_edge = 0.0
            decision = EdgeDecision.HOLD
            reason = ""

            for pred in predictions:
                thresholds = self.inferencer.get_threshold(pred.horizon)
                buy_thr = float(thresholds.get("buy_threshold", 0.0))
                sell_thr = float(thresholds.get("sell_threshold", 0.0))
                edge_buy = pred.predicted_price - ask
                edge_sell = bid - pred.predicted_price

                if pred.predicted_return >= buy_thr and edge_buy > best_edge:
                    best_edge = edge_buy
                    decision = EdgeDecision.BUY
                    reason = (
                        f"{pred.horizon.value}: pred={pred.predicted_price:.4f} > ask={ask:.4f}"
                    )

                if pred.predicted_return <= sell_thr and edge_sell > best_edge:
                    best_edge = edge_sell
                    decision = EdgeDecision.SELL
                    reason = (
                        f"{pred.horizon.value}: pred={pred.predicted_price:.4f} < bid={bid:.4f}"
                    )

            # Store signal for API
            self.last_signals[market_id] = Signal(
                market_id=market_id,
                timestamp=state.updated_at or datetime.now(UTC),
                current_mid=mid,
                current_bid=bid,
                current_ask=ask,
                predictions=predictions,
                edge=best_edge,
                decision=decision,
                strategy=self.name,
                reason=reason,
            )

            # Check if edge beats costs
            breakeven = estimate_breakeven_edge(mid, spread)
            required_edge = breakeven + self.edge_buffer

            if best_edge < required_edge:
                continue  # Not enough edge

            # Position sizing
            current_pos = portfolio.positions.get(market_id)
            current_size = current_pos.size if current_pos else 0.0

            if decision == EdgeDecision.BUY and current_size <= 0:
                size = self._kelly_size(best_edge, mid, portfolio)
                if size > 0:
                    orders.append(
                        Order(
                            market_id=market_id,
                            side=Side.BUY,
                            size=size,
                            strategy=self.name,
                            edge=best_edge,
                        )
                    )

            elif decision == EdgeDecision.SELL and current_size > 0:
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.SELL,
                        size=current_size,
                        strategy=self.name,
                        edge=best_edge,
                    )
                )

        return orders
