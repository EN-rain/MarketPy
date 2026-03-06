"""Unit tests for automation engine failure behavior."""

from __future__ import annotations

import pytest

from backend.app.automation.engine import AutomationEngine
from backend.app.automation.models import ActionType, AutomatedAction, RiskLimits


@pytest.mark.asyncio
async def test_automation_engine_halts_and_notifies_on_failure() -> None:
    notifications: list[str] = []

    async def notifier(message: str) -> bool:
        notifications.append(message)
        return True

    async def failing_executor(_: AutomatedAction) -> dict[str, bool]:
        raise RuntimeError("boom")

    engine = AutomationEngine(error_notifier=notifier)
    engine.register_executor(ActionType.PLACE_ORDER, failing_executor)

    action = AutomatedAction(
        id="a1",
        market_id="BTCUSDT",
        action_type=ActionType.PLACE_ORDER,
        parameters={"price": 10.0, "size": 1.0},
        risk_limits=RiskLimits(
            max_order_notional=1000.0,
            max_position_notional=10_000.0,
            max_daily_loss=1000.0,
            allowed_markets=["BTCUSDT"],
        ),
    )

    first = await engine.execute_action(action, portfolio_state={"position_notional": 0.0})
    second = await engine.execute_action(action, portfolio_state={"position_notional": 0.0})

    assert first["status"] == "FAILED"
    assert second["status"] == "SKIPPED"
    assert second["message"] == "kill_switch_engaged"
    assert engine.kill_switch.engaged is True
    assert notifications and "automation failure" in notifications[0]
