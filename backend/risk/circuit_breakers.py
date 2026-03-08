"""Circuit breakers for extreme market conditions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CircuitBreakerStatus:
    flash_crash: bool
    liquidation_cascade: bool
    exchange_outage: bool
    drawdown_breaker: bool

    @property
    def triggered(self) -> bool:
        return self.flash_crash or self.liquidation_cascade or self.exchange_outage or self.drawdown_breaker


class CircuitBreakerManager:
    """Evaluates hard-stop market conditions."""

    @staticmethod
    def flash_crash_triggered(price_move_pct_1m: float) -> bool:
        return abs(float(price_move_pct_1m)) > 0.10

    @staticmethod
    def liquidation_cascade_triggered(liquidation_volume: float, average_liquidation_volume: float) -> bool:
        if average_liquidation_volume <= 0:
            return False
        return liquidation_volume > average_liquidation_volume * 10.0

    @staticmethod
    def exchange_outage_triggered(outage_seconds: float) -> bool:
        return float(outage_seconds) > 10.0

    def evaluate(
        self,
        *,
        price_move_pct_1m: float,
        liquidation_volume: float,
        average_liquidation_volume: float,
        outage_seconds: float,
        drawdown: float,
    ) -> CircuitBreakerStatus:
        return CircuitBreakerStatus(
            flash_crash=self.flash_crash_triggered(price_move_pct_1m),
            liquidation_cascade=self.liquidation_cascade_triggered(liquidation_volume, average_liquidation_volume),
            exchange_outage=self.exchange_outage_triggered(outage_seconds),
            drawdown_breaker=drawdown >= 0.20,
        )
