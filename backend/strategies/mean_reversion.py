"""Mean reversion strategy using z-score of price vs SMA."""

from __future__ import annotations

import math

from backend.app.models.market import MarketState, Side
from backend.app.models.portfolio import Portfolio
from backend.sim.engine import Order
from backend.strategies.base import Strategy


class MeanReversionStrategy(Strategy):
    """Z-score mean reversion strategy.

    z = (mid - SMA(mid, N)) / STD(mid, N)

    Buy when z < -z_entry (price is abnormally low).
    Sell when z > z_entry (price is abnormally high).
    Exit positions when z returns to within z_exit of zero.

    Args:
        lookback: Number of bars for SMA and STD calculation.
        z_entry: Z-score threshold to enter a position.
        z_exit: Z-score threshold to exit a position.
        order_size: Fixed order size per trade.
    """

    name = "mean_reversion"

    def __init__(
        self,
        lookback: int = 20,
        z_entry: float = 2.0,
        z_exit: float = 0.5,
        order_size: float = 100.0,
    ) -> None:
        self.lookback = lookback
        self.z_entry = z_entry
        self.z_exit = z_exit
        self.order_size = order_size

    def _compute_zscore(self, prices: list[float]) -> float | None:
        """Compute z-score of the last price relative to the window."""
        if len(prices) < self.lookback:
            return None

        window = prices[-self.lookback :]
        mean = sum(window) / len(window)
        variance = sum((p - mean) ** 2 for p in window) / len(window)
        std = math.sqrt(variance) if variance > 0 else 0

        if std < 1e-9:
            return 0.0

        return (prices[-1] - mean) / std

    def on_bar(
        self,
        markets: dict[str, MarketState],
        portfolio: Portfolio,
    ) -> list[Order]:
        orders: list[Order] = []

        for market_id, state in markets.items():
            if len(state.candles) < self.lookback:
                continue

            prices = [c.mid for c in state.candles]
            z = self._compute_zscore(prices)

            if z is None:
                continue

            current_pos = 0.0
            pos = portfolio.positions.get(market_id)
            if pos is not None:
                current_pos = pos.size

            if z < -self.z_entry and current_pos <= 0:
                # Price is abnormally low — buy (expect reversion up)
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.BUY,
                        size=self.order_size,
                        strategy=self.name,
                        edge=abs(z),
                    )
                )
            elif z > self.z_entry and current_pos > 0:
                # Price is abnormally high — sell (expect reversion down)
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.SELL,
                        size=current_pos,
                        strategy=self.name,
                        edge=abs(z),
                    )
                )
            elif abs(z) < self.z_exit and current_pos > 0:
                # Z-score returned to normal — close position
                orders.append(
                    Order(
                        market_id=market_id,
                        side=Side.SELL,
                        size=current_pos,
                        strategy=self.name,
                        edge=abs(z),
                    )
                )

        return orders
