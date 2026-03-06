"""Event-driven simulation engine.

Iterates through bars chronologically, updating market state,
calling the strategy for order decisions, processing fills,
and updating the portfolio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

from backend.app.models.config import AppSettings, settings
from backend.app.models.market import Candle, MarketInfo, MarketState, OrderBookSnapshot, Side
from backend.app.models.portfolio import Portfolio
from backend.sim.fill_model import FillModelLevel, fill_order
from backend.sim.portfolio import PortfolioManager

logger = logging.getLogger(__name__)


@dataclass
class Order:
    """An order to be placed by a strategy."""

    market_id: str
    side: Side
    size: float
    limit_price: float | None = None
    strategy: str = "manual"
    edge: float | None = None


@dataclass
class SimResult:
    """Result from a completed simulation run."""

    portfolio: Portfolio
    duration_bars: int = 0
    markets_processed: int = 0
    orders_submitted: int = 0
    orders_filled: int = 0
    errors: list[str] = field(default_factory=list)


class SimEngine:
    """Core event-driven simulation engine.

    Usage:
        engine = SimEngine(config=settings)
        engine.add_market(market_info, candles)
        result = engine.run(strategy)
    """

    def __init__(self, config: AppSettings | None = None) -> None:
        self.config = config or settings
        self.pm = PortfolioManager(initial_cash=self.config.initial_cash)
        self.markets: dict[str, MarketState] = {}
        self._candle_data: dict[str, list[Candle]] = {}

    def add_market(self, info: MarketInfo, candles: list[Candle]) -> None:
        """Add a market with its historical candle data for backtesting."""
        market_id = info.condition_id
        self.markets[market_id] = MarketState(info=info)
        self._candle_data[market_id] = sorted(candles, key=lambda c: c.timestamp)
        logger.info(f"Added market {market_id}: {len(candles)} bars")

    def run(self, strategy) -> SimResult:
        """Run the simulation over all bars.

        Args:
            strategy: A strategy object with an `on_bar(states, portfolio) -> list[Order]` method.

        Returns:
            SimResult with final portfolio and stats.
        """
        result = SimResult(
            portfolio=self.pm.portfolio,
            markets_processed=len(self.markets),
        )

        # Build a unified timeline of all bars across markets
        timeline: list[tuple[datetime, str, Candle]] = []
        for market_id, candles in self._candle_data.items():
            for candle in candles:
                timeline.append((candle.timestamp, market_id, candle))

        timeline.sort(key=lambda x: x[0])

        if not timeline:
            logger.warning("No candle data — nothing to simulate")
            return result

        logger.info(f"Simulation: {len(timeline)} bars across {len(self.markets)} markets")

        fill_model_setting = self.config.fill_model
        fill_model_name = (
            fill_model_setting.value if hasattr(fill_model_setting, "value") else str(fill_model_setting)
        )
        fill_model = FillModelLevel(fill_model_name)

        for ts, market_id, candle in timeline:
            result.duration_bars += 1

            # Update market state with current bar
            state = self.markets[market_id]
            ob = OrderBookSnapshot(
                token_id=state.info.token_id_yes,
                timestamp=candle.timestamp,
                best_bid=candle.bid,
                best_ask=candle.ask,
                mid=candle.mid,
                spread=candle.spread,
            )
            state.orderbook = ob
            state.candles.append(candle)
            state.last_trade_price = candle.close
            state.updated_at = candle.timestamp

            # Compute time_to_close if end_date is known
            if state.info.end_date:
                delta = (state.info.end_date - candle.timestamp).total_seconds()
                state.time_to_close = max(0, delta)

            # Ask strategy for orders
            try:
                orders = strategy.on_bar(self.markets, self.pm.portfolio)
            except Exception as e:
                logger.error(f"Strategy error at {ts}: {e}")
                result.errors.append(f"{ts}: {e}")
                continue

            # Process orders
            for order in orders:
                result.orders_submitted += 1

                order_state = self.markets.get(order.market_id)
                if order_state is None or order_state.orderbook is None:
                    continue

                # Risk checks
                if self.pm.check_daily_loss_limit(self.config.max_daily_loss):
                    logger.warning(f"Daily loss limit hit at {ts}")
                    continue

                if order.side == Side.BUY and self.pm.check_max_exposure(
                    self.config.max_total_exposure
                ):
                    continue

                current_size = self.pm.get_position_size(order.market_id)
                if (
                    order.side == Side.BUY
                    and current_size + order.size > self.config.max_position_per_market
                ):
                    continue

                # Fill
                fill = fill_order(
                    side=order.side,
                    size=order.size,
                    orderbook=order_state.orderbook,
                    model=fill_model,
                    fee_rate=self.config.default_fee_rate,
                    fee_exponent=self.config.default_fee_exponent,
                    limit_price=order.limit_price,
                )

                if fill.filled:
                    self.pm.record_fill(
                        market_id=order.market_id,
                        side=order.side,
                        fill=fill,
                        strategy=order.strategy,
                        edge=order.edge,
                        timestamp=candle.timestamp,
                    )
                    result.orders_filled += 1

            # Mark to market at end of each bar
            prices = {}
            for mid, ms in self.markets.items():
                if ms.orderbook and ms.orderbook.mid is not None:
                    prices[mid] = ms.orderbook.mid
            self.pm.mark_to_market(prices, timestamp=candle.timestamp)

        result.portfolio = self.pm.portfolio
        logger.info(
            f"Simulation complete: {result.duration_bars} bars, "
            f"{result.orders_filled}/{result.orders_submitted} fills, "
            f"PnL: {self.pm.portfolio.total_pnl:.2f}"
        )
        return result
