"""Reusable position sizing with Kelly, regime, and confidence adjustments."""

from __future__ import annotations

from dataclasses import dataclass

from backend.regime.parameters import RegimeParameterManager


@dataclass(frozen=True, slots=True)
class PositionSizeResult:
    size: float
    raw_kelly_fraction: float
    applied_fraction: float


class PositionSizer:
    """Computes position sizes using a bounded fractional Kelly approach."""

    def __init__(self, kelly_fraction: float = 0.1, min_position_fraction: float = 0.01) -> None:
        self.kelly_fraction = kelly_fraction
        self.min_position_fraction = min_position_fraction
        self.regime_parameters = RegimeParameterManager()

    def compute_kelly_size(
        self,
        *,
        edge: float,
        volatility: float,
        portfolio_value: float,
        regime: str = "ranging",
        confidence: float = 1.0,
    ) -> PositionSizeResult:
        if edge <= 0 or volatility <= 0 or portfolio_value <= 0:
            return PositionSizeResult(0.0, 0.0, 0.0)

        raw_kelly_fraction = edge / max(volatility**2, 1e-9)
        params = self.regime_parameters.get_regime_parameters(regime)
        applied_fraction = raw_kelly_fraction * self.kelly_fraction
        applied_fraction *= max(0.0, min(1.0, confidence))
        applied_fraction *= params.position_size_multiplier
        applied_fraction = max(0.0, min(0.20, applied_fraction))

        size = portfolio_value * applied_fraction
        minimum_size = portfolio_value * self.min_position_fraction
        if size > 0:
            size = max(minimum_size, size)
        size = min(size, portfolio_value * 0.20)

        return PositionSizeResult(
            size=float(size),
            raw_kelly_fraction=float(raw_kelly_fraction),
            applied_fraction=float(applied_fraction),
        )
