"""Portfolio risk calculations for VaR, concentration, leverage, and correlations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.app.risk.correlation_calculator import CorrelationCalculator, CorrelationMatrix
from backend.app.risk.var_calculator import VaRCalculator, VaRMethod, VaRResult


@dataclass(frozen=True, slots=True)
class PortfolioRiskSnapshot:
    var_result: VaRResult
    cvar_percent: float
    concentration_risk: float
    leverage: float
    correlation_matrix: CorrelationMatrix


class PortfolioRiskManager:
    """Aggregates core portfolio-level risk metrics."""

    def __init__(self) -> None:
        self.var_calculator = VaRCalculator()
        self.correlation_calculator = CorrelationCalculator(window_days=30)
        self._last_correlation_at: datetime | None = None

    def compute_var(
        self,
        portfolio_value: float,
        returns: list[float],
        confidence_level: float = 0.95,
        method: VaRMethod = VaRMethod.HISTORICAL,
    ) -> VaRResult:
        return self.var_calculator.calculate_var(
            portfolio_value=portfolio_value,
            returns=returns,
            confidence_level=confidence_level,
            method=method,
        )

    def compute_cvar(self, returns: list[float], confidence_level: float = 0.95) -> float:
        losses = sorted(max(0.0, -value) for value in returns)
        if not losses:
            return 0.0
        cutoff = max(1, int(len(losses) * confidence_level))
        tail = losses[cutoff - 1 :]
        return float(sum(tail) / len(tail))

    def compute_correlation_matrix(self, returns_by_asset: dict[str, list[float]]) -> CorrelationMatrix:
        self._last_correlation_at = datetime.now()
        return self.correlation_calculator.calculate_correlations(returns_by_asset)

    def should_recompute_correlation(self, now: datetime) -> bool:
        if self._last_correlation_at is None:
            return True
        return now - self._last_correlation_at >= timedelta(hours=4)

    @staticmethod
    def compute_concentration_risk(position_values: dict[str, float]) -> float:
        total = sum(max(0.0, value) for value in position_values.values())
        if total <= 0:
            return 0.0
        weights = [max(0.0, value) / total for value in position_values.values()]
        return float(sum(weight * weight for weight in weights))

    @staticmethod
    def compute_leverage(position_values: dict[str, float], portfolio_equity: float) -> float:
        if portfolio_equity <= 0:
            return 0.0
        gross = sum(abs(value) for value in position_values.values())
        return float(gross / portfolio_equity)

    def snapshot(
        self,
        *,
        portfolio_value: float,
        returns: list[float],
        returns_by_asset: dict[str, list[float]],
        position_values: dict[str, float],
    ) -> PortfolioRiskSnapshot:
        var_result = self.compute_var(portfolio_value, returns, 0.95, VaRMethod.HISTORICAL)
        return PortfolioRiskSnapshot(
            var_result=var_result,
            cvar_percent=self.compute_cvar(returns, 0.95),
            concentration_risk=self.compute_concentration_risk(position_values),
            leverage=self.compute_leverage(position_values, portfolio_value),
            correlation_matrix=self.compute_correlation_matrix(returns_by_asset),
        )
