"""Position-level risk limit checks."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.risk.correlation_calculator import CorrelationMatrix


@dataclass(frozen=True, slots=True)
class PositionLimitResult:
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    leverage: float = 0.0
    largest_position_pct: float = 0.0
    correlated_exposure_pct: float = 0.0


class PositionRiskManager:
    """Enforces portfolio-wide position constraints."""

    def check_position_limits(
        self,
        *,
        position_values: dict[str, float],
        portfolio_value: float,
        correlation_matrix: CorrelationMatrix,
        maintenance_margin_ratio: float = 2.0,
    ) -> PositionLimitResult:
        if portfolio_value <= 0:
            return PositionLimitResult(False, ["portfolio_value_non_positive"])

        reasons: list[str] = []
        gross = sum(abs(value) for value in position_values.values())
        leverage = gross / portfolio_value
        if leverage > 3.0:
            reasons.append("max_leverage_exceeded")

        largest_position_pct = max((abs(value) / portfolio_value for value in position_values.values()), default=0.0)
        if largest_position_pct > 0.20:
            reasons.append("single_position_limit_exceeded")

        correlated_exposure = 0.0
        assets = correlation_matrix.assets
        for i, asset_a in enumerate(assets):
            for j, asset_b in enumerate(assets):
                if j <= i:
                    continue
                if abs(correlation_matrix.matrix[i][j]) > 0.7:
                    correlated_exposure = max(
                        correlated_exposure,
                        (abs(position_values.get(asset_a, 0.0)) + abs(position_values.get(asset_b, 0.0)))
                        / portfolio_value,
                    )
        if correlated_exposure > 0.40:
            reasons.append("correlated_position_limit_exceeded")

        if maintenance_margin_ratio < 1.5:
            reasons.append("margin_ratio_below_minimum")

        return PositionLimitResult(
            allowed=not reasons,
            reasons=reasons,
            leverage=float(leverage),
            largest_position_pct=float(largest_position_pct),
            correlated_exposure_pct=float(correlated_exposure),
        )
