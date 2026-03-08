"""Portfolio manager — handles position tracking, PnL, and equity curve."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from backend.app.models.market import Side
from backend.app.models.portfolio import (
    EquityPoint,
    Portfolio,
    Position,
    Trade,
    TradeAction,
)
from backend.sim.fill_model import FillResult

logger = logging.getLogger(__name__)


class PortfolioManager:
    """Manages portfolio state: positions, cash, PnL, equity curve."""

    def __init__(self, initial_cash: float = 10000.0) -> None:
        self.portfolio = Portfolio(cash=initial_cash, initial_cash=initial_cash)
        self._peak_equity: float = initial_cash
        now = datetime.now(UTC)
        self._daily_loss_anchor_date = now.date()
        self._daily_loss_anchor_equity = initial_cash

    def record_fill(
        self,
        market_id: str,
        side: Side,
        fill: FillResult,
        strategy: str = "manual",
        edge: float | None = None,
        timestamp: datetime | None = None,
    ) -> Trade:
        """Record a filled order and update portfolio state.

        Args:
            market_id: The market this trade is for.
            side: BUY or SELL.
            fill: The fill result from the fill model.
            strategy: Name of the strategy that generated this trade.
            edge: The predicted edge at time of trade.
            timestamp: Trade timestamp.

        Returns:
            The Trade object that was recorded.
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        action = TradeAction.BUY_YES if side == Side.BUY else TradeAction.SELL_YES

        # Calculate realized PnL for closing trades
        realized_pnl = None
        pos = self.portfolio.positions.get(market_id)

        if side == Side.BUY:
            # Buying: decrease cash by (price * size + fee)
            cost = fill.fill_price * fill.fill_size + fill.fee
            self.portfolio.cash -= cost

            # Update or create position
            if pos is None:
                pos = Position(
                    market_id=market_id,
                    side="YES",
                    size=fill.fill_size,
                    avg_entry_price=(fill.fill_price * fill.fill_size + fill.fee) / fill.fill_size,
                    current_price=fill.fill_price,
                )
                self.portfolio.positions[market_id] = pos
            else:
                # Average up
                total_cost = pos.avg_entry_price * pos.size + (
                    fill.fill_price * fill.fill_size + fill.fee
                )
                pos.size += fill.fill_size
                pos.avg_entry_price = total_cost / pos.size if pos.size > 0 else 0
                pos.current_price = fill.fill_price

        else:  # SELL
            if pos is not None and pos.size > 0:
                sell_size = min(fill.fill_size, pos.size)
                # Revenue from selling
                revenue = fill.fill_price * sell_size - fill.fee
                self.portfolio.cash += revenue

                # Realized PnL
                realized_pnl = (fill.fill_price - pos.avg_entry_price) * sell_size - fill.fee
                pos.realized_pnl += realized_pnl
                pos.size -= sell_size
                pos.current_price = fill.fill_price

                # Remove position if fully closed
                if pos.size <= 1e-9:
                    del self.portfolio.positions[market_id]
            else:
                logger.warning(
                    "Ignoring SELL fill for market '%s': no open position to close",
                    market_id,
                )

        self.portfolio.total_fees_paid += fill.fee

        trade = Trade(
            id=str(uuid.uuid4())[:8],
            timestamp=timestamp,
            market_id=market_id,
            action=action,
            price=fill.fill_price,
            size=fill.fill_size,
            fee=fill.fee,
            strategy=strategy,
            edge=edge,
            pnl=realized_pnl,
        )
        self.portfolio.trades.append(trade)
        return trade

    def mark_to_market(
        self,
        market_prices: dict[str, float],
        timestamp: datetime | None = None,
    ) -> None:
        """Update all position prices and record equity curve point.

        Args:
            market_prices: {market_id: current_mid_price}
            timestamp: Current timestamp.
        """
        if timestamp is None:
            timestamp = datetime.now(UTC)

        for market_id, price in market_prices.items():
            pos = self.portfolio.positions.get(market_id)
            if pos is not None:
                pos.current_price = price
                pos.unrealized_pnl = (price - pos.avg_entry_price) * pos.size

        total_equity = self.portfolio.total_equity
        self._peak_equity = max(self._peak_equity, total_equity)
        drawdown = (
            (self._peak_equity - total_equity) / self._peak_equity if self._peak_equity > 0 else 0
        )

        point = EquityPoint(
            timestamp=timestamp,
            cash=self.portfolio.cash,
            positions_value=self.portfolio.positions_value,
            total_equity=total_equity,
            drawdown=drawdown,
        )
        self.portfolio.equity_curve.append(point)

    def check_daily_loss_limit(self, max_daily_loss: float) -> bool:
        """Return True if daily loss limit has been breached."""
        today = datetime.now(UTC).date()
        if today != self._daily_loss_anchor_date:
            self._daily_loss_anchor_date = today
            self._daily_loss_anchor_equity = self.portfolio.total_equity

        daily_loss = self._daily_loss_anchor_equity - self.portfolio.total_equity
        return daily_loss > max_daily_loss

    def check_max_exposure(self, max_exposure: float) -> bool:
        """Return True if total exposure exceeds the limit."""
        return self.portfolio.positions_value > max_exposure

    def get_position_size(self, market_id: str) -> float:
        """Return current position size for a market (0 if no position)."""
        pos = self.portfolio.positions.get(market_id)
        return pos.size if pos else 0.0
