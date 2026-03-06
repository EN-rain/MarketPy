"""Stress testing engine for risk cockpit scenarios."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class StressScenario:
    name: str
    asset_shocks: dict[str, float]
    correlation_matrix: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass(frozen=True)
class StressResult:
    scenario_name: str
    timestamp: datetime
    base_value: float
    stressed_value: float
    value_change: float
    value_change_percent: float
    position_impacts: dict[str, float]


class StressTester:
    """Runs predefined and custom stress scenarios."""

    def __init__(self) -> None:
        self.scenarios: dict[str, StressScenario] = self._default_scenarios()

    def _default_scenarios(self) -> dict[str, StressScenario]:
        return {
            "2008_crisis": StressScenario(
                name="2008_crisis",
                asset_shocks={
                    "BTC": -0.45,
                    "ETH": -0.5,
                    "SOL": -0.6,
                    "SPY": -0.35,
                    "NDX": -0.4,
                },
                correlation_matrix={
                    "BTC": {"ETH": 0.78, "SPY": 0.45},
                    "ETH": {"SOL": 0.82},
                },
            ),
            "covid_crash": StressScenario(
                name="covid_crash",
                asset_shocks={
                    "BTC": -0.35,
                    "ETH": -0.38,
                    "SOL": -0.45,
                    "SPY": -0.28,
                    "NDX": -0.31,
                },
                correlation_matrix={
                    "BTC": {"ETH": 0.81, "SPY": 0.52},
                    "ETH": {"SOL": 0.84},
                },
            ),
            "flash_crash": StressScenario(
                name="flash_crash",
                asset_shocks={
                    "BTC": -0.18,
                    "ETH": -0.22,
                    "SOL": -0.3,
                    "SPY": -0.08,
                    "NDX": -0.11,
                },
                correlation_matrix={
                    "BTC": {"ETH": 0.75, "SPY": 0.34},
                    "ETH": {"SOL": 0.8},
                },
            ),
        }

    def register_scenario(self, scenario: StressScenario) -> None:
        self.scenarios[scenario.name] = scenario

    def run_stress_test(
        self,
        positions: dict[str, float],
        scenario_name: str | None = None,
        scenario: StressScenario | None = None,
    ) -> StressResult:
        active = scenario or self.scenarios.get(scenario_name or "")
        if active is None:
            raise ValueError("unknown stress scenario")

        base_value = float(sum(positions.values()))
        impacts: dict[str, float] = {}
        for asset, notional in positions.items():
            shock = active.asset_shocks.get(asset, 0.0)
            impacts[asset] = float(notional) * shock

        value_change = sum(impacts.values())
        stressed_value = base_value + value_change
        change_pct = 0.0 if base_value == 0 else value_change / base_value

        return StressResult(
            scenario_name=active.name,
            timestamp=datetime.now(UTC),
            base_value=base_value,
            stressed_value=stressed_value,
            value_change=value_change,
            value_change_percent=change_pct,
            position_impacts=impacts,
        )

    def suggest_adjustments(
        self,
        result: StressResult,
        positions: dict[str, float],
        max_drawdown_percent: float = 0.2,
    ) -> list[str]:
        if abs(result.value_change_percent) <= max_drawdown_percent:
            return []

        ranked = sorted(
            positions.items(),
            key=lambda item: abs(result.position_impacts.get(item[0], 0.0)),
            reverse=True,
        )
        suggestions: list[str] = []
        for asset, notional in ranked[:3]:
            impact = result.position_impacts.get(asset, 0.0)
            if impact >= 0:
                continue
            cut = min(0.5, abs(result.value_change_percent) / max(0.01, max_drawdown_percent))
            suggestions.append(
                "Reduce "
                f"{asset} exposure by {cut * 100:.1f}% "
                f"(position={notional:.2f}, impact={impact:.2f})"
            )

        if not suggestions:
            suggestions.append("Rebalance into lower-volatility assets or add hedges.")
        return suggestions
