"""Derivatives-specific margin and liquidation risk controls."""

from __future__ import annotations

from dataclasses import dataclass

from backend.ingest.exchanges.base import MarginAccount, PerpetualPosition


@dataclass(frozen=True, slots=True)
class DerivativesRiskSnapshot:
    margin_ratio: float
    liquidation_buffer: float
    liquidation_risk: float
    requires_reduction: bool
    reduction_factor: float


class DerivativesRiskManager:
    """Risk controls for leveraged derivative positions."""

    def monitor_margin(self, account: MarginAccount) -> float:
        return float(account.margin_ratio)

    def liquidation_risk(
        self,
        *,
        current_price: float,
        liquidation_price: float,
        side: str,
    ) -> float:
        if current_price <= 0:
            return 1.0
        if side.lower() == "short":
            buffer = max(liquidation_price - current_price, 0.0) / current_price
        else:
            buffer = max(current_price - liquidation_price, 0.0) / current_price
        return float(max(0.0, 1.0 - min(buffer / 0.2, 1.0)))

    def position_reduction_factor(self, margin_ratio: float, threshold: float = 1.2) -> float:
        if margin_ratio >= threshold:
            return 1.0
        if margin_ratio <= 0:
            return 0.0
        return float(max(0.0, min(1.0, margin_ratio / threshold)))

    def snapshot(self, account: MarginAccount, position: PerpetualPosition) -> DerivativesRiskSnapshot:
        mark_price = position.mark_price or position.entry_price
        notional = max(position.notional_value or (mark_price * position.quantity), 1e-9)
        maintenance = max(position.maintenance_margin or account.maintenance_margin, 1e-9)
        inferred_liquidation = mark_price - (maintenance / max(position.quantity or 1.0, 1e-9))
        liquidation_risk = self.liquidation_risk(
            current_price=mark_price,
            liquidation_price=inferred_liquidation,
            side=position.side,
        )
        buffer = abs(mark_price - inferred_liquidation) / max(mark_price, 1e-9)
        reduction_factor = self.position_reduction_factor(account.margin_ratio)
        return DerivativesRiskSnapshot(
            margin_ratio=float(account.margin_ratio),
            liquidation_buffer=float(buffer),
            liquidation_risk=float(liquidation_risk),
            requires_reduction=account.margin_ratio < 1.2,
            reduction_factor=float(reduction_factor),
        )
