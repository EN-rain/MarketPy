"""Momentum strategy — buy when recent returns are positive, sell when negative."""

from __future__ import annotations

from backend.app.models.market import MarketState, Side
from backend.app.models.portfolio import Portfolio
from backend.sim.engine import Order
from backend.strategies.base import Strategy


class MomentumStrategy(Strategy):
    """Simple momentum strategy.

    Buy if the return over the lookback period exceeds a positive threshold.
    Sell if it drops below the negative threshold.

    Args:
        lookback: Number of bars to compute return over.
        threshold: Minimum absolute return to trigger a trade.
        order_size: Fixed order size per trade.
    """

    name = "momentum"

    def __init__(
        self,
        lookback: int = 12,
        threshold: float = 0.01,
        order_size: float = 100.0,
    ) -> None:
        self.lookback = lookback
        self.threshold = threshold
        self.order_size = order_size

    def on_bar(
        self,
        markets: dict[str, MarketState],
        portfolio: Portfolio,
    ) -> list[Order]:
        orders: list[Order] = []

        for market_id, state in markets.items():
            if len(state.candles) < self.lookback + 1:
                continue

            # Compute return over lookback period
            current_mid = state.candles[-1].mid
            past_mid = state.candles[-(self.lookback + 1)].mid

            if past_mid <= 0:
                continue

            ret = (current_mid - past_mid) / past_mid

            current_pos = 0.0
            pos = portfolio.positions.get(market_id)
            if pos is not None:
                current_pos = pos.size

            if ret > self.threshold and current_pos <= 0:
                # Bullish momentum — buy
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.BUY,
                        size=self.order_size,
                        strategy=self.name,
                        edge=ret,
                    )
                )
            elif ret < -self.threshold and current_pos > 0:
                # Bearish momentum — sell
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.SELL,
                        size=current_pos,  # close entire position
                        strategy=self.name,
                        edge=ret,
                    )
                )

        return orders
