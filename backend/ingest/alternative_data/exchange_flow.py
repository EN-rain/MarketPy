"""Exchange flow analytics for potential pressure signals."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class ExchangeFlowSnapshot:
    symbol: str
    inflow: float
    outflow: float
    netflow: float
    price_correlation: float


class ExchangeFlowAnalyzer:
    def analyze(self, symbol: str, frame: pd.DataFrame) -> ExchangeFlowSnapshot:
        if frame.empty:
            return ExchangeFlowSnapshot(symbol=symbol, inflow=0.0, outflow=0.0, netflow=0.0, price_correlation=0.0)
        inflow = pd.to_numeric(frame.get("exchange_inflow", 0.0), errors="coerce").fillna(0.0)
        outflow = pd.to_numeric(frame.get("exchange_outflow", 0.0), errors="coerce").fillna(0.0)
        netflow = inflow - outflow
        close = pd.to_numeric(frame.get("close", 0.0), errors="coerce").fillna(0.0)
        returns = close.pct_change().fillna(0.0)
        corr = float(netflow.corr(returns)) if len(netflow) > 1 else 0.0
        if pd.isna(corr):
            corr = 0.0
        return ExchangeFlowSnapshot(
            symbol=symbol,
            inflow=float(inflow.sum()),
            outflow=float(outflow.sum()),
            netflow=float(netflow.sum()),
            price_correlation=corr,
        )
