"""Regime-adaptive parameter selection."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegimeParameters:
    profit_target_multiplier: float
    stop_loss_multiplier: float
    position_size_multiplier: float


DEFAULT_REGIME_PARAMETERS: dict[str, RegimeParameters] = {
    "trending_up": RegimeParameters(1.3, 0.9, 1.1),
    "trending_down": RegimeParameters(1.1, 0.8, 0.9),
    "ranging": RegimeParameters(0.9, 0.9, 0.8),
    "high_volatility": RegimeParameters(0.8, 0.7, 0.6),
    "low_volatility": RegimeParameters(1.0, 1.1, 1.0),
    "crisis": RegimeParameters(0.6, 0.6, 0.4),
}


class RegimeParameterManager:
    """Provides parameter overrides based on the current regime."""

    def __init__(self, parameters: dict[str, RegimeParameters] | None = None) -> None:
        self.parameters = parameters or DEFAULT_REGIME_PARAMETERS.copy()

    def get_regime_parameters(self, regime: str) -> RegimeParameters:
        return self.parameters.get(regime, RegimeParameters(1.0, 1.0, 1.0))

    def adjust(self, regime: str, *, profit_target: float, stop_loss: float, position_size: float) -> dict[str, float]:
        params = self.get_regime_parameters(regime)
        return {
            "profit_target": profit_target * params.profit_target_multiplier,
            "stop_loss": stop_loss * params.stop_loss_multiplier,
            "position_size": position_size * params.position_size_multiplier,
        }
