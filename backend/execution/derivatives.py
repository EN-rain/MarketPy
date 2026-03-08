"""Derivatives support for perpetuals, options, and strategy helpers."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime

from backend.ingest.alternative_data.integrator import AlternativeDataIntegrator
from backend.ingest.exchanges.base import MarginAccount, OptionContract, PerpetualPosition


@dataclass(frozen=True, slots=True)
class PerpetualSnapshot:
    symbol: str
    funding_rate: float
    position: PerpetualPosition
    margin_account: MarginAccount


@dataclass(frozen=True, slots=True)
class OptionQuote:
    contract: OptionContract
    theoretical_price: float
    delta: float
    gamma: float
    theta: float
    vega: float


class DerivativesEngine:
    """Shared derivatives helpers across exchange adapters and risk controls."""

    def __init__(self, alt_data_integrator: AlternativeDataIntegrator | None = None) -> None:
        self.alt_data_integrator = alt_data_integrator or AlternativeDataIntegrator()

    async def perpetual_snapshot(self, adapter, symbol: str) -> PerpetualSnapshot:
        funding = await adapter.get_funding_rates([symbol])
        positions = await adapter.get_perpetual_positions()
        margin_account = await adapter.get_margin_account()
        position = next((item for item in positions if item.symbol == symbol), None)
        if position is None:
            position = PerpetualPosition(
                symbol=symbol,
                side="flat",
                quantity=0.0,
                entry_price=0.0,
                mark_price=0.0,
                leverage=1.0,
                unrealized_pnl=0.0,
                funding_rate=funding.get(symbol, 0.0),
                margin_ratio=margin_account.margin_ratio,
                maintenance_margin=margin_account.maintenance_margin,
                notional_value=0.0,
            )
        return PerpetualSnapshot(
            symbol=symbol,
            funding_rate=float(funding.get(symbol, 0.0)),
            position=position,
            margin_account=margin_account,
        )

    @staticmethod
    def _norm_cdf(value: float) -> float:
        return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))

    @staticmethod
    def _norm_pdf(value: float) -> float:
        return math.exp(-(value**2) / 2.0) / math.sqrt(2.0 * math.pi)

    def black_scholes(
        self,
        *,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: str,
    ) -> float:
        if time_to_expiry <= 0 or volatility <= 0 or spot <= 0 or strike <= 0:
            intrinsic = max(spot - strike, 0.0) if option_type == "call" else max(strike - spot, 0.0)
            return float(intrinsic)
        d1 = (math.log(spot / strike) + (rate + 0.5 * volatility * volatility) * time_to_expiry) / (
            volatility * math.sqrt(time_to_expiry)
        )
        d2 = d1 - volatility * math.sqrt(time_to_expiry)
        if option_type == "call":
            return float(spot * self._norm_cdf(d1) - strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(d2))
        return float(strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(-d2) - spot * self._norm_cdf(-d1))

    def binomial_price(
        self,
        *,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: str,
        steps: int = 50,
    ) -> float:
        if steps <= 0:
            raise ValueError("steps must be positive")
        dt = max(time_to_expiry / steps, 1e-9)
        up = math.exp(volatility * math.sqrt(dt))
        down = 1.0 / up
        discount = math.exp(-rate * dt)
        probability = max(0.0, min(1.0, (math.exp(rate * dt) - down) / max(up - down, 1e-9)))
        payoffs = []
        for index in range(steps + 1):
            terminal = spot * (up ** (steps - index)) * (down**index)
            payoff = max(terminal - strike, 0.0) if option_type == "call" else max(strike - terminal, 0.0)
            payoffs.append(payoff)
        for step in range(steps, 0, -1):
            payoffs = [
                discount * (probability * payoffs[node] + (1.0 - probability) * payoffs[node + 1])
                for node in range(step)
            ]
        return float(payoffs[0])

    def greeks(
        self,
        *,
        spot: float,
        strike: float,
        time_to_expiry: float,
        rate: float,
        volatility: float,
        option_type: str,
    ) -> dict[str, float]:
        if time_to_expiry <= 0 or volatility <= 0 or spot <= 0 or strike <= 0:
            delta = 1.0 if option_type == "call" and spot > strike else -1.0 if option_type == "put" and spot < strike else 0.0
            return {"delta": delta, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
        d1 = (math.log(spot / strike) + (rate + 0.5 * volatility * volatility) * time_to_expiry) / (
            volatility * math.sqrt(time_to_expiry)
        )
        d2 = d1 - volatility * math.sqrt(time_to_expiry)
        pdf = self._norm_pdf(d1)
        delta = self._norm_cdf(d1) if option_type == "call" else self._norm_cdf(d1) - 1.0
        gamma = pdf / (spot * volatility * math.sqrt(time_to_expiry))
        theta_base = -(spot * pdf * volatility) / (2.0 * math.sqrt(time_to_expiry))
        if option_type == "call":
            theta = theta_base - rate * strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(d2)
        else:
            theta = theta_base + rate * strike * math.exp(-rate * time_to_expiry) * self._norm_cdf(-d2)
        vega = spot * pdf * math.sqrt(time_to_expiry)
        return {"delta": float(delta), "gamma": float(gamma), "theta": float(theta), "vega": float(vega)}

    def option_quote(
        self,
        contract: OptionContract,
        *,
        spot: float,
        rate: float = 0.02,
        valuation_time: datetime | None = None,
    ) -> OptionQuote:
        now = valuation_time or datetime.now(UTC)
        time_to_expiry = max((contract.expiry - now).total_seconds(), 0.0) / (365.0 * 24.0 * 60.0 * 60.0)
        theoretical_price = self.black_scholes(
            spot=spot,
            strike=contract.strike,
            time_to_expiry=time_to_expiry,
            rate=rate,
            volatility=max(contract.implied_volatility, 1e-6),
            option_type=contract.option_type,
        )
        greeks = self.greeks(
            spot=spot,
            strike=contract.strike,
            time_to_expiry=time_to_expiry,
            rate=rate,
            volatility=max(contract.implied_volatility, 1e-6),
            option_type=contract.option_type,
        )
        return OptionQuote(
            contract=contract,
            theoretical_price=theoretical_price,
            delta=greeks["delta"],
            gamma=greeks["gamma"],
            theta=greeks["theta"],
            vega=greeks["vega"],
        )

    def covered_call(self, spot_position: float, call_contract: OptionContract, premium: float) -> dict[str, float]:
        covered_notional = min(max(spot_position, 0.0), 1.0)
        return {
            "covered_ratio": covered_notional,
            "max_profit": premium + max(call_contract.strike - call_contract.mark_price, 0.0),
            "downside_buffer": premium,
        }

    def protective_put(self, spot_position: float, put_contract: OptionContract, premium: float) -> dict[str, float]:
        protected_notional = min(max(spot_position, 0.0), 1.0)
        return {
            "protected_ratio": protected_notional,
            "floor_price": put_contract.strike - premium,
            "premium_cost": premium,
        }

    def vertical_spread(self, long_leg: OptionQuote, short_leg: OptionQuote) -> dict[str, float]:
        net_premium = long_leg.theoretical_price - short_leg.theoretical_price
        width = abs(long_leg.contract.strike - short_leg.contract.strike)
        return {
            "net_premium": net_premium,
            "max_profit": max(width - net_premium, 0.0),
            "max_loss": max(net_premium, 0.0),
        }
