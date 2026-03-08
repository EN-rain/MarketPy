"""Property tests for stress testing engine."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.risk.stress_tester import StressScenario, StressTester

POSITION_MAP = st.dictionaries(
    keys=st.sampled_from(["BTC", "ETH", "SOL", "SPY", "NDX"]),
    values=st.floats(min_value=0.0, max_value=2_000_000.0, allow_nan=False, allow_infinity=False),
    min_size=1,
    max_size=5,
)


# Property 28: Stress Test Value Change
@given(positions=POSITION_MAP)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_stress_test_value_change(positions: dict[str, float]) -> None:
    tester = StressTester()
    result = tester.run_stress_test(positions, scenario_name="2008_crisis")

    for asset, notional in positions.items():
        shock = tester.scenarios["2008_crisis"].asset_shocks.get(asset, 0.0)
        assert result.position_impacts[asset] == pytest.approx(notional * shock)

    expected_change = sum(result.position_impacts.values())
    assert result.value_change == pytest.approx(expected_change)
    assert result.stressed_value == pytest.approx(result.base_value + expected_change)


# Property 29: Stress Test Risk Suggestions
@given(
    btc=st.floats(min_value=10_000.0, max_value=2_000_000.0, allow_nan=False, allow_infinity=False),
    eth=st.floats(min_value=10_000.0, max_value=2_000_000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_stress_test_risk_suggestions(btc: float, eth: float) -> None:
    tester = StressTester()
    positions = {"BTC": btc, "ETH": eth}
    severe = StressScenario(
        name="severe_custom",
        asset_shocks={"BTC": -0.7, "ETH": -0.8},
        correlation_matrix={"BTC": {"ETH": 0.9}},
    )
    result = tester.run_stress_test(positions, scenario=severe)
    suggestions = tester.suggest_adjustments(result, positions, max_drawdown_percent=0.2)
    assert suggestions
