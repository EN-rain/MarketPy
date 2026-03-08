"""Unified risk manager interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.regime.parameters import RegimeParameterManager
from backend.risk.circuit_breakers import CircuitBreakerManager, CircuitBreakerStatus
from backend.risk.crypto_risk import CryptoRiskManager, CryptoRiskSnapshot
from backend.risk.derivatives_risk import DerivativesRiskManager, DerivativesRiskSnapshot
from backend.risk.drawdown import DrawdownController, DrawdownStatus
from backend.risk.portfolio_risk import PortfolioRiskManager, PortfolioRiskSnapshot
from backend.risk.position_risk import PositionLimitResult, PositionRiskManager
from backend.strategies.position_sizing import PositionSizer


@dataclass(frozen=True, slots=True)
class RiskDecision:
    portfolio: PortfolioRiskSnapshot
    positions: PositionLimitResult
    drawdown: DrawdownStatus
    crypto: CryptoRiskSnapshot
    derivatives: DerivativesRiskSnapshot | None
    circuit_breakers: CircuitBreakerStatus
    adjusted_position_size: float


class RiskManager:
    """Integrates portfolio, position, drawdown, and crypto risk checks."""

    def __init__(self) -> None:
        self.portfolio_risk = PortfolioRiskManager()
        self.position_risk = PositionRiskManager()
        self.drawdown = DrawdownController()
        self.crypto_risk = CryptoRiskManager()
        self.derivatives_risk = DerivativesRiskManager()
        self.circuit_breakers = CircuitBreakerManager()
        self.regime_parameters = RegimeParameterManager()
        self.position_sizer = PositionSizer()

    def adjust_limits_for_regime(self, regime: str, base_position_size: float) -> float:
        params = self.regime_parameters.get_regime_parameters(regime)
        if regime in {"high_volatility", "crisis"}:
            return float(base_position_size * params.position_size_multiplier)
        return float(base_position_size * min(1.0, params.position_size_multiplier))

    def compute_portfolio_risk(
        self,
        *,
        portfolio_value: float,
        returns: list[float],
        returns_by_asset: dict[str, list[float]],
        position_values: dict[str, float],
    ) -> PortfolioRiskSnapshot:
        return self.portfolio_risk.snapshot(
            portfolio_value=portfolio_value,
            returns=returns,
            returns_by_asset=returns_by_asset,
            position_values=position_values,
        )

    def check_position_limits(
        self,
        *,
        position_values: dict[str, float],
        portfolio_value: float,
        correlation_matrix,
        maintenance_margin_ratio: float,
    ) -> PositionLimitResult:
        return self.position_risk.check_position_limits(
            position_values=position_values,
            portfolio_value=portfolio_value,
            correlation_matrix=correlation_matrix,
            maintenance_margin_ratio=maintenance_margin_ratio,
        )

    def adjust_position_size(
        self,
        *,
        base_position_size: float,
        regime: str,
        margin_ratio: float,
        drawdown: float,
        portfolio_value: float | None = None,
        edge: float | None = None,
        volatility: float | None = None,
        confidence: float = 1.0,
    ) -> float:
        if portfolio_value is not None and edge is not None and volatility is not None:
            size = self.position_sizer.compute_kelly_size(
                edge=edge,
                volatility=volatility,
                portfolio_value=portfolio_value,
                regime=regime,
                confidence=confidence,
            ).size
            size = min(size, base_position_size)
        else:
            size = self.adjust_limits_for_regime(regime, base_position_size)
        size *= self.crypto_risk.reduce_for_margin_ratio(margin_ratio)
        if drawdown >= 0.20:
            return 0.0
        if drawdown >= 0.10:
            size *= 0.5
        return float(max(0.0, size))

    def evaluate_all(
        self,
        *,
        portfolio_value: float,
        returns: list[float],
        returns_by_asset: dict[str, list[float]],
        position_values: dict[str, float],
        maintenance_margin_ratio: float,
        current_equity: float,
        regime: str,
        stablecoin_price: float,
        contract_metadata: dict[str, Any],
        exchange_metadata: dict[str, Any],
        current_price: float,
        liquidation_price: float,
        price_move_pct_1m: float,
        liquidation_volume: float,
        average_liquidation_volume: float,
        outage_seconds: float,
        base_position_size: float,
        derivatives_account=None,
        derivatives_position=None,
    ) -> RiskDecision:
        portfolio = self.compute_portfolio_risk(
            portfolio_value=portfolio_value,
            returns=returns,
            returns_by_asset=returns_by_asset,
            position_values=position_values,
        )
        positions = self.check_position_limits(
            position_values=position_values,
            portfolio_value=portfolio_value,
            correlation_matrix=portfolio.correlation_matrix,
            maintenance_margin_ratio=maintenance_margin_ratio,
        )
        drawdown_status = self.drawdown.check_drawdown_limits(
            current_equity=current_equity,
            position_values=position_values,
        )
        crypto = self.crypto_risk.snapshot(
            stablecoin_price=stablecoin_price,
            contract_metadata=contract_metadata,
            exchange_metadata=exchange_metadata,
            current_price=current_price,
            liquidation_price=liquidation_price,
            margin_ratio=maintenance_margin_ratio,
        )
        circuit_breakers = self.circuit_breakers.evaluate(
            price_move_pct_1m=price_move_pct_1m,
            liquidation_volume=liquidation_volume,
            average_liquidation_volume=average_liquidation_volume,
            outage_seconds=outage_seconds,
            drawdown=drawdown_status.drawdown,
        )
        derivatives = None
        if derivatives_account is not None and derivatives_position is not None:
            derivatives = self.derivatives_risk.snapshot(derivatives_account, derivatives_position)
        adjusted_size = self.adjust_position_size(
            base_position_size=base_position_size,
            regime=regime,
            margin_ratio=maintenance_margin_ratio,
            drawdown=drawdown_status.drawdown,
            portfolio_value=portfolio_value,
            edge=max(0.0, portfolio.var_result.var_percent),
            volatility=max(1e-6, portfolio.cvar_percent),
            confidence=max(0.0, min(1.0, 1.0 - portfolio.var_result.var_percent)),
        )

        return RiskDecision(
            portfolio=portfolio,
            positions=positions,
            drawdown=drawdown_status,
            crypto=crypto,
            derivatives=derivatives,
            circuit_breakers=circuit_breakers,
            adjusted_position_size=adjusted_size,
        )
