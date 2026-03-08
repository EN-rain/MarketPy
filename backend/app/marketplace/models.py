"""Marketplace data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VerifiedMetrics:
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    out_of_sample_period_days: int


@dataclass(frozen=True)
class MarketplaceStrategy:
    id: str
    name: str
    author: str
    description: str
    asset_class: str
    risk_level: str
    methodology: str
    metrics: VerifiedMetrics
