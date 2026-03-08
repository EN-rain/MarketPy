"""Property tests for Automation Hub engine."""

from __future__ import annotations

from datetime import UTC

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.automation.engine import AutomationEngine
from backend.app.automation.models import ActionType, AutomatedAction, RiskLimits


async def _executor(_: AutomatedAction) -> dict[str, bool]:
    return {"ok": True}


# Property 25: Automated Action Risk Validation
@given(
    max_order=st.floats(min_value=10.0, max_value=10_000.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.01, max_value=1_000.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_automated_action_risk_validation(max_order: float, delta: float) -> None:
    engine = AutomationEngine()
    engine.register_executor(ActionType.PLACE_ORDER, _executor)

    price = 1.0
    size = max_order + delta
    action = AutomatedAction(
        id="auto-risk",
        market_id="BTCUSDT",
        action_type=ActionType.PLACE_ORDER,
        parameters={"price": price, "size": size},
        risk_limits=RiskLimits(
            max_order_notional=max_order,
            max_position_notional=max_order * 10,
            max_daily_loss=max_order * 10,
            allowed_markets=["BTCUSDT"],
        ),
    )

    result = await engine.execute_action(action, portfolio_state={"position_notional": 0.0})
    assert result["status"] == "REJECTED"
    assert result["message"] == "order_notional_limit_exceeded"


# Property 26: Automated Action Logging
@given(action_count=st.integers(min_value=1, max_value=25))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_automated_action_logging(action_count: int) -> None:
    engine = AutomationEngine()
    engine.register_executor(ActionType.PLACE_ORDER, _executor)

    limits = RiskLimits(
        max_order_notional=1000.0,
        max_position_notional=10_000.0,
        max_daily_loss=5000.0,
        allowed_markets=["BTCUSDT"],
    )
    for index in range(action_count):
        if index % 2 == 0:
            params = {"price": 10.0, "size": 5.0}
        else:
            params = {"price": 10.0, "size": 500.0}
        action = AutomatedAction(
            id=f"act-{index}",
            market_id="BTCUSDT",
            action_type=ActionType.PLACE_ORDER,
            parameters=params,
            risk_limits=limits,
        )
        await engine.execute_action(action, portfolio_state={"position_notional": 100.0})

    assert len(engine.action_log) == action_count
    assert all(entry.action_id for entry in engine.action_log)
    assert all(entry.market_id == "BTCUSDT" for entry in engine.action_log)
    assert all(entry.timestamp.tzinfo is UTC for entry in engine.action_log)
    assert all(entry.message for entry in engine.action_log)
