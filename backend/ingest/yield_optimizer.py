"""Yield tracking and simple optimizer across DeFi protocols."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class YieldVenue:
    protocol: str
    apr: float
    liquidity: float
    lock_days: int = 0


class YieldOptimizer:
    def best_venue(self, venues: list[YieldVenue]) -> YieldVenue | None:
        if not venues:
            return None
        return max(venues, key=lambda venue: (venue.apr, venue.liquidity, -venue.lock_days))

    def rebalance_plan(self, capital: float, venues: list[YieldVenue]) -> dict[str, float]:
        best = self.best_venue(venues)
        if best is None:
            return {}
        return {best.protocol: float(capital)}
