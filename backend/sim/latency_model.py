"""Latency model for realistic order submission/fill timing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum

import numpy as np


class LatencyDistribution(str, Enum):
    FIXED = "fixed"
    UNIFORM = "uniform"
    NORMAL = "normal"
    EXPONENTIAL = "exponential"


@dataclass(slots=True)
class DistributionConfig:
    distribution: LatencyDistribution = LatencyDistribution.NORMAL
    fixed_ms: float = 50.0
    min_ms: float = 10.0
    max_ms: float = 500.0
    mean_ms: float = 50.0
    std_ms: float = 10.0


@dataclass(slots=True)
class LatencyConfig:
    network: DistributionConfig = field(
        default_factory=lambda: DistributionConfig(
            distribution=LatencyDistribution.NORMAL,
            min_ms=10.0,
            max_ms=500.0,
            mean_ms=60.0,
            std_ms=20.0,
            fixed_ms=60.0,
        )
    )
    exchange: DistributionConfig = field(
        default_factory=lambda: DistributionConfig(
            distribution=LatencyDistribution.UNIFORM,
            min_ms=5.0,
            max_ms=100.0,
            mean_ms=20.0,
            std_ms=10.0,
            fixed_ms=20.0,
        )
    )


class LatencyModel:
    """Samples network/exchange latency and applies it to order timestamps."""

    def __init__(self, config: LatencyConfig | None = None, random_seed: int | None = None) -> None:
        self.config = config or LatencyConfig()
        self._rng = np.random.default_rng(seed=random_seed)

    def _sample(self, cfg: DistributionConfig) -> float:
        if cfg.distribution == LatencyDistribution.FIXED:
            value = cfg.fixed_ms
        elif cfg.distribution == LatencyDistribution.UNIFORM:
            value = float(self._rng.uniform(cfg.min_ms, cfg.max_ms))
        elif cfg.distribution == LatencyDistribution.NORMAL:
            value = float(self._rng.normal(cfg.mean_ms, cfg.std_ms))
        else:
            scale = max(cfg.mean_ms, 1.0)
            value = float(self._rng.exponential(scale=scale))
        return float(np.clip(value, cfg.min_ms, cfg.max_ms))

    def sample_network_latency(self) -> float:
        value = self._sample(self.config.network)
        return float(np.clip(value, 10.0, 500.0))

    def sample_exchange_latency(self) -> float:
        value = self._sample(self.config.exchange)
        return float(np.clip(value, 5.0, 100.0))

    def apply_to_order(self, signal_time):
        network_ms = self.sample_network_latency()
        exchange_ms = self.sample_exchange_latency()
        submission_time = signal_time + timedelta(milliseconds=network_ms)
        fill_time = submission_time + timedelta(milliseconds=exchange_ms)
        return submission_time, fill_time

    @staticmethod
    def adjust_price_for_latency(intended_price: float, observed_prices: list[float], side: str) -> float:
        """Pick next available price when intended quote is missed due to latency."""
        if not observed_prices:
            return intended_price
        if side.upper() == "BUY":
            candidates = [price for price in observed_prices if price >= intended_price]
            return min(candidates) if candidates else max(observed_prices)
        candidates = [price for price in observed_prices if price <= intended_price]
        return max(candidates) if candidates else min(observed_prices)
