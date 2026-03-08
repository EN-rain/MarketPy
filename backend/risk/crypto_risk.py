"""Crypto-specific risk controls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CryptoRiskSnapshot:
    stablecoin_depeg: bool
    smart_contract_risk: float
    exchange_counterparty_risk: float
    liquidation_distance: float
    margin_ratio_reduction: float


class CryptoRiskManager:
    """Handles crypto-native risks such as depegs and liquidation distance."""

    def detect_depeg(self, price: float, peg: float = 1.0, threshold: float = 0.02) -> bool:
        return abs(float(price) - float(peg)) > threshold

    def assess_smart_contract_risk(self, metadata: dict[str, Any]) -> float:
        audits = float(metadata.get("audit_count", 0))
        critical_issues = float(metadata.get("critical_issues", 0))
        admin_keys = 1.0 if metadata.get("has_admin_keys", False) else 0.0
        score = max(0.0, min(1.0, 0.7 - 0.15 * audits + 0.2 * critical_issues + 0.1 * admin_keys))
        return float(score)

    def assess_exchange_counterparty_risk(self, metadata: dict[str, Any]) -> float:
        uptime = float(metadata.get("uptime", 1.0))
        proof_of_reserves = 0.0 if metadata.get("proof_of_reserves", True) else 0.2
        regulatory = 0.0 if metadata.get("regulated", True) else 0.1
        score = max(0.0, min(1.0, (1.0 - uptime) + proof_of_reserves + regulatory))
        return float(score)

    def calculate_liquidation_distance(
        self,
        *,
        current_price: float,
        liquidation_price: float,
    ) -> float:
        if current_price <= 0:
            return 0.0
        return float(abs(current_price - liquidation_price) / current_price)

    def reduce_for_margin_ratio(self, margin_ratio: float) -> float:
        if margin_ratio >= 1.5:
            return 1.0
        if margin_ratio <= 1.0:
            return 0.0
        return float(max(0.0, min(1.0, (margin_ratio - 1.0) / 0.5)))

    def snapshot(
        self,
        *,
        stablecoin_price: float,
        contract_metadata: dict[str, Any],
        exchange_metadata: dict[str, Any],
        current_price: float,
        liquidation_price: float,
        margin_ratio: float,
    ) -> CryptoRiskSnapshot:
        return CryptoRiskSnapshot(
            stablecoin_depeg=self.detect_depeg(stablecoin_price),
            smart_contract_risk=self.assess_smart_contract_risk(contract_metadata),
            exchange_counterparty_risk=self.assess_exchange_counterparty_risk(exchange_metadata),
            liquidation_distance=self.calculate_liquidation_distance(
                current_price=current_price,
                liquidation_price=liquidation_price,
            ),
            margin_ratio_reduction=self.reduce_for_margin_ratio(margin_ratio),
        )
