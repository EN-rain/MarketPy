"""Property tests for strategy marketplace."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.marketplace.marketplace import StrategyMarketplace
from backend.app.marketplace.models import MarketplaceStrategy, VerifiedMetrics


# Property 59: Strategy Performance Verification
@given(
    returns=st.lists(
        st.floats(min_value=-0.1, max_value=0.2, allow_nan=False, allow_infinity=False),
        min_size=180,
        max_size=400,
    ),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_strategy_performance_verification(returns: list[float]) -> None:
    with TemporaryDirectory() as tmp_dir:
        marketplace = StrategyMarketplace(str(Path(tmp_dir) / "marketplace.db"))
        try:
            metrics = marketplace.verify_performance(returns, out_of_sample_days=180)
            assert isinstance(metrics.total_return, float)
            assert isinstance(metrics.sharpe_ratio, float)
            assert 0.0 <= metrics.max_drawdown <= 1.0
        finally:
            marketplace.close()


# Property 60: Strategy Out-of-Sample Requirement
@given(days=st.integers(min_value=1, max_value=179))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_strategy_out_of_sample_requirement(days: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        marketplace = StrategyMarketplace(str(Path(tmp_dir) / "marketplace.db"))
        try:
            metrics = VerifiedMetrics(
                total_return=0.1,
                sharpe_ratio=1.0,
                max_drawdown=0.2,
                out_of_sample_period_days=days,
            )
            strategy = MarketplaceStrategy(
                id="s1",
                name="S",
                author="A",
                description="D",
                asset_class="crypto",
                risk_level="medium",
                methodology="m",
                metrics=metrics,
            )
            with pytest.raises(ValueError, match="out_of_sample period must be >= 180 days"):
                marketplace.submit_strategy(strategy)
        finally:
            marketplace.close()
