"""Phase 12 risk management tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.risk.var_calculator import VaRMethod
from backend.risk.portfolio_risk import PortfolioRiskManager
from backend.risk.position_risk import PositionRiskManager


RETURN_LISTS = st.lists(
    st.floats(min_value=-0.2, max_value=0.2, allow_nan=False, allow_infinity=False),
    min_size=30,
    max_size=120,
)


def test_portfolio_and_position_risk_checkpoint() -> None:
    portfolio = PortfolioRiskManager()
    position = PositionRiskManager()
    returns = [0.01, -0.02, 0.015, -0.01, 0.005] * 10
    returns_by_asset = {
        "BTC": returns,
        "ETH": [value * 0.9 for value in returns],
        "SOL": [value * -0.2 for value in returns],
    }
    positions = {"BTC": 8_000.0, "ETH": 7_000.0, "SOL": 4_000.0}

    snapshot = portfolio.snapshot(
        portfolio_value=50_000.0,
        returns=returns,
        returns_by_asset=returns_by_asset,
        position_values=positions,
    )
    assert snapshot.var_result.var_percent >= 0.0
    assert snapshot.cvar_percent >= snapshot.var_result.var_percent
    assert snapshot.leverage <= 1.0
    assert snapshot.concentration_risk > 0.0
    assert portfolio.should_recompute_correlation(datetime.now()) is False

    limit = position.check_position_limits(
        position_values=positions,
        portfolio_value=50_000.0,
        correlation_matrix=snapshot.correlation_matrix,
        maintenance_margin_ratio=2.0,
    )
    assert limit.allowed is True


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    btc=RETURN_LISTS,
    eth=RETURN_LISTS,
    sol=RETURN_LISTS,
)
def test_property_correlation_matrix_symmetry(btc: list[float], eth: list[float], sol: list[float]) -> None:
    n = min(len(btc), len(eth), len(sol))
    calc = PortfolioRiskManager()
    matrix = calc.compute_correlation_matrix(
        {"BTC": btc[:n], "ETH": eth[:n], "SOL": sol[:n]}
    )
    for i in range(len(matrix.assets)):
        assert matrix.matrix[i][i] == pytest.approx(1.0, abs=1e-9) or abs(matrix.matrix[i][i]) <= 1.0
        for j in range(len(matrix.assets)):
            assert matrix.matrix[i][j] == pytest.approx(matrix.matrix[j][i], abs=1e-9)


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    portfolio_value=st.floats(min_value=10_000.0, max_value=2_000_000.0, allow_nan=False, allow_infinity=False),
    returns=RETURN_LISTS,
)
def test_property_var_confidence_level(portfolio_value: float, returns: list[float]) -> None:
    manager = PortfolioRiskManager()
    result_95 = manager.compute_var(portfolio_value, returns, 0.95, VaRMethod.HISTORICAL)
    result_99 = manager.compute_var(portfolio_value, returns, 0.99, VaRMethod.HISTORICAL)
    assert result_99.var_percent >= result_95.var_percent
    assert result_99.var_dollar >= result_95.var_dollar


@pytest.mark.property_test
@settings(max_examples=25)
@given(
    portfolio_value=st.floats(min_value=1_000.0, max_value=100_000.0, allow_nan=False, allow_infinity=False),
    gross_multiplier=st.floats(min_value=0.1, max_value=5.0, allow_nan=False, allow_infinity=False),
)
def test_property_portfolio_leverage_limit(portfolio_value: float, gross_multiplier: float) -> None:
    manager = PositionRiskManager()
    exposure = portfolio_value * gross_multiplier
    positions = {"BTC": exposure * 0.6, "ETH": exposure * 0.4}
    corr = PortfolioRiskManager().compute_correlation_matrix(
        {"BTC": [0.01] * 30, "ETH": [0.01] * 30}
    )
    result = manager.check_position_limits(
        position_values=positions,
        portfolio_value=portfolio_value,
        correlation_matrix=corr,
        maintenance_margin_ratio=2.0,
    )
    if result.leverage > 3.0:
        assert "max_leverage_exceeded" in result.reasons
    else:
        assert "max_leverage_exceeded" not in result.reasons
