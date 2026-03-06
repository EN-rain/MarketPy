"""Pydantic models for AI signals and predictions."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class Horizon(str, Enum):
    H1 = "1h"
    H6 = "6h"
    D1 = "1d"


class Prediction(BaseModel):
    """A single price prediction for one horizon."""

    horizon: Horizon
    predicted_return: float  # log return
    predicted_price: float  # mid * exp(predicted_return)
    confidence: float = 0.0  # model confidence / feature importance


class EdgeDecision(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class Signal(BaseModel):
    """Complete signal for a market combining predictions + edge analysis."""

    market_id: str
    timestamp: datetime
    current_mid: float
    current_bid: float
    current_ask: float
    predictions: list[Prediction]
    edge: float  # best prediction edge over current price
    decision: EdgeDecision = EdgeDecision.HOLD
    strategy: str = "ai"
    reason: str = ""

    @property
    def edge_pct(self) -> float:
        if self.current_mid == 0:
            return 0.0
        return (self.edge / self.current_mid) * 100
