"""Tests for portfolio manager."""

import pytest

from backend.app.models.market import Side
from backend.sim.fill_model import FillResult
from backend.sim.portfolio import PortfolioManager


class TestPortfolioManager:
    def setup_method(self):
        self.pm = PortfolioManager(initial_cash=10000.0)

    def test_initial_state(self):
        assert self.pm.portfolio.cash == 10000.0
        assert self.pm.portfolio.total_equity == 10000.0
        assert len(self.pm.portfolio.positions) == 0
        assert len(self.pm.portfolio.trades) == 0

    def test_buy_creates_position(self):
        fill = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0.01)
        self.pm.record_fill("market1", Side.BUY, fill)

        assert "market1" in self.pm.portfolio.positions
        pos = self.pm.portfolio.positions["market1"]
        assert pos.size == 100
        assert pos.avg_entry_price == pytest.approx(0.6001, abs=1e-6)
        assert self.pm.portfolio.cash < 10000.0

    def test_sell_closes_position(self):
        # Buy first
        buy_fill = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0.01)
        self.pm.record_fill("market1", Side.BUY, buy_fill)

        # Sell
        sell_fill = FillResult(filled=True, fill_price=0.65, fill_size=100, fee=0.01)
        trade = self.pm.record_fill("market1", Side.SELL, sell_fill)

        assert "market1" not in self.pm.portfolio.positions
        assert trade.pnl is not None
        assert trade.pnl > 0  # sold higher than bought
        assert self.pm.portfolio.realized_pnl == pytest.approx(trade.pnl, abs=1e-9)

    def test_fees_tracked(self):
        fill = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0.05)
        self.pm.record_fill("market1", Side.BUY, fill)
        assert self.pm.portfolio.total_fees_paid == 0.05

    def test_mark_to_market(self):
        fill = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0.01)
        self.pm.record_fill("market1", Side.BUY, fill)

        self.pm.mark_to_market({"market1": 0.70})

        pos = self.pm.portfolio.positions["market1"]
        assert pos.current_price == 0.70
        assert pos.unrealized_pnl > 0

        assert len(self.pm.portfolio.equity_curve) == 1

    def test_drawdown_tracking(self):
        fill = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0)
        self.pm.record_fill("market1", Side.BUY, fill)

        # Price goes up then down
        self.pm.mark_to_market({"market1": 0.80})
        self.pm.mark_to_market({"market1": 0.50})

        assert self.pm.portfolio.equity_curve[-1].drawdown > 0

    def test_average_entry_price(self):
        # Buy 100 at 0.60
        fill1 = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0)
        self.pm.record_fill("market1", Side.BUY, fill1)

        # Buy 100 more at 0.70
        fill2 = FillResult(filled=True, fill_price=0.70, fill_size=100, fee=0)
        self.pm.record_fill("market1", Side.BUY, fill2)

        pos = self.pm.portfolio.positions["market1"]
        assert pos.size == 200
        assert pos.avg_entry_price == pytest.approx(0.65, abs=0.001)

    def test_daily_loss_limit(self):
        # Large losing trade
        buy_fill = FillResult(filled=True, fill_price=0.90, fill_size=10000, fee=0)
        self.pm.record_fill("market1", Side.BUY, buy_fill)

        self.pm.mark_to_market({"market1": 0.10})

        assert self.pm.check_daily_loss_limit(500.0) is True

    def test_sell_without_position_is_ignored_but_recorded(self):
        fill = FillResult(filled=True, fill_price=0.60, fill_size=100, fee=0.01)
        trade = self.pm.record_fill("market-missing", Side.SELL, fill)
        assert trade.pnl is None
        assert self.pm.get_position_size("market-missing") == 0.0
