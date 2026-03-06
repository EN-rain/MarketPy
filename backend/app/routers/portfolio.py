"""Portfolio endpoint — cash, positions, equity, PnL."""

from __future__ import annotations

from fastapi import APIRouter

from backend.app.models.portfolio import Portfolio

router = APIRouter()

# In-memory portfolio (will be replaced by sim engine state)
_portfolio = Portfolio()


@router.get("/portfolio")
async def get_portfolio():
    """Return current portfolio state."""
    return {
        "cash": _portfolio.cash,
        "initial_cash": _portfolio.initial_cash,
        "total_equity": _portfolio.total_equity,
        "total_pnl": _portfolio.total_pnl,
        "total_pnl_pct": _portfolio.total_pnl_pct,
        "total_fees_paid": _portfolio.total_fees_paid,
        "positions_count": len(_portfolio.positions),
        "positions": {
            mid: {
                "side": pos.side,
                "size": pos.size,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": pos.current_price,
                "unrealized_pnl": pos.unrealized_pnl,
                "realized_pnl": pos.realized_pnl,
                "market_value": pos.market_value,
            }
            for mid, pos in _portfolio.positions.items()
        },
        "max_drawdown": _portfolio.max_drawdown,
        "win_rate": _portfolio.win_rate,
        "trade_count": len(_portfolio.trades),
    }
