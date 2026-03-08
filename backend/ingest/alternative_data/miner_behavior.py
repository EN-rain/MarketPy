"""Miner wallet behavior analytics."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class MinerBehaviorSnapshot:
    symbol: str
    balance_change: float
    selling_pressure: float
    hashrate_correlation: float


class MinerBehaviorAnalyzer:
    def analyze(self, symbol: str, frame: pd.DataFrame) -> MinerBehaviorSnapshot:
        if frame.empty:
            return MinerBehaviorSnapshot(symbol=symbol, balance_change=0.0, selling_pressure=0.0, hashrate_correlation=0.0)

        balances = pd.to_numeric(frame.get("miner_balance", 0.0), errors="coerce").fillna(0.0)
        hash_rate = pd.to_numeric(frame.get("hash_rate_eh_s", 0.0), errors="coerce").fillna(0.0)
        balance_diff = balances.diff().fillna(0.0)
        negative = balance_diff[balance_diff < 0.0].abs()
        selling_pressure = float(negative.sum())
        correlation = float(balance_diff.corr(hash_rate.pct_change().fillna(0.0))) if len(frame) > 1 else 0.0
        if pd.isna(correlation):
            correlation = 0.0
        return MinerBehaviorSnapshot(
            symbol=symbol,
            balance_change=float(balances.iloc[-1] - balances.iloc[0]),
            selling_pressure=selling_pressure,
            hashrate_correlation=correlation,
        )
