"""DeFi-specific risk controls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DeFiRiskSnapshot:
    smart_contract_score: float
    impermanent_loss: float
    gas_risk: float
    mev_risk: float


class DeFiRiskManager:
    def assess_smart_contract_risk(self, audit_score: float, tvl: float, exploit_history: int) -> float:
        score = (0.6 * audit_score) + (0.3 * min(tvl / 1_000_000.0, 1.0)) - (0.2 * exploit_history)
        return float(max(0.0, min(1.0, score)))

    def impermanent_loss(self, price_ratio: float) -> float:
        if price_ratio <= 0:
            return 1.0
        il = (2.0 * (price_ratio**0.5) / (1.0 + price_ratio)) - 1.0
        return float(abs(il))

    def gas_risk(self, gas_price_gwei: float, target_gas_price_gwei: float) -> float:
        if target_gas_price_gwei <= 0:
            return 1.0
        return float(max(0.0, gas_price_gwei / target_gas_price_gwei - 1.0))

    def mev_risk(self, slippage_bps: float, pool_depth: float) -> float:
        return float(max(0.0, (slippage_bps / 100.0) / max(pool_depth, 1.0)))

    def snapshot(
        self,
        *,
        audit_score: float,
        tvl: float,
        exploit_history: int,
        price_ratio: float,
        gas_price_gwei: float,
        target_gas_price_gwei: float,
        slippage_bps: float,
        pool_depth: float,
    ) -> DeFiRiskSnapshot:
        return DeFiRiskSnapshot(
            smart_contract_score=self.assess_smart_contract_risk(audit_score, tvl, exploit_history),
            impermanent_loss=self.impermanent_loss(price_ratio),
            gas_risk=self.gas_risk(gas_price_gwei, target_gas_price_gwei),
            mev_risk=self.mev_risk(slippage_bps, pool_depth),
        )
