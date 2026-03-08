"""Signals endpoint — AI predictions + edge + decision."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

router = APIRouter()

# In-memory signals (populated by AI strategy)
_signals: dict = {}


@router.get("/signals/{market_id}")
async def get_signals(market_id: str):
    """Return latest AI signals for a market."""
    signal = _signals.get(market_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"No signals for market {market_id}")

    return {
        "market_id": signal.market_id,
        "timestamp": signal.timestamp.isoformat(),
        "current_mid": signal.current_mid,
        "current_bid": signal.current_bid,
        "current_ask": signal.current_ask,
        "predictions": [
            {
                "horizon": p.horizon.value,
                "predicted_return": round(p.predicted_return, 6),
                "predicted_price": round(p.predicted_price, 4),
                "confidence": round(p.confidence, 4),
            }
            for p in signal.predictions
        ],
        "edge": round(signal.edge, 6),
        "edge_pct": round(signal.edge_pct, 4),
        "decision": signal.decision.value,
        "strategy": signal.strategy,
        "reason": signal.reason,
    }
