"""Trades endpoint — recent fills."""

from __future__ import annotations

from fastapi import APIRouter, Query

router = APIRouter()

# In-memory trades (populated by sim engine)
_trades: list = []


@router.get("/trades")
async def get_trades(
    limit: int = Query(default=50, ge=1, le=500),
    market_id: str | None = None,
):
    """Return recent trades, optionally filtered by market."""
    trades = list(_trades)

    try:
        from backend.app.routers.paper_trading import get_paper_engine

        paper_engine = get_paper_engine()
        if paper_engine is not None:
            trades.extend(paper_engine.portfolio.trades)
    except Exception:
        pass

    if market_id:
        trades = [t for t in trades if t.market_id == market_id]

    # Return most recent first
    recent = sorted(trades, key=lambda t: t.timestamp, reverse=True)[:limit]
    return [
        {
            "id": t.id,
            "timestamp": t.timestamp.isoformat(),
            "market_id": t.market_id,
            "action": t.action.value,
            "price": round(t.price, 4),
            "size": round(t.size, 4),
            "fee": round(t.fee, 6),
            "strategy": t.strategy,
            "edge": round(t.edge, 6) if t.edge is not None else None,
            "pnl": round(t.pnl, 4) if t.pnl is not None else None,
        }
        for t in recent
    ]
