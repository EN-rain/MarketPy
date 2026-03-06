"""Property tests for Alerting Hub engine."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.alerts.engine import AlertEngine
from backend.app.alerts.models import AlertCondition, ConditionType, Operator


# Property 22: Alert Condition Evaluation
@given(
    threshold=st.floats(min_value=0.1, max_value=1000.0, allow_nan=False, allow_infinity=False),
    delta=st.floats(min_value=0.01, max_value=500.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_alert_condition_evaluation(threshold: float, delta: float) -> None:
    engine = AlertEngine()
    condition = AlertCondition(
        id="c1",
        market_id="BTCUSDT",
        condition_type=ConditionType.PRICE,
        operator=Operator.GT,
        threshold=threshold,
        cooldown_seconds=0.0,
        channels=["webhook"],
    )
    engine.register_condition(condition)
    engine.register_notifier("webhook", lambda _: _ok())  # type: ignore[arg-type]

    triggered = await engine.evaluate_conditions("BTCUSDT", {"mid": threshold + delta})
    assert len(triggered) == 1
    assert triggered[0].observed_value > threshold


async def _ok() -> bool:
    return True


# Property 23: Alert Notification Delivery
@given(channel_count=st.integers(min_value=1, max_value=4))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_alert_notification_delivery(channel_count: int) -> None:
    engine = AlertEngine()
    channels = [f"ch{i}" for i in range(channel_count)]
    condition = AlertCondition(
        id="c2",
        market_id="BTCUSDT",
        condition_type=ConditionType.VOLUME,
        operator=Operator.GT,
        threshold=1.0,
        cooldown_seconds=0.0,
        channels=channels,
    )
    engine.register_condition(condition)

    calls = {"count": 0}

    async def notifier(_):
        calls["count"] += 1
        return True

    for channel in channels:
        engine.register_notifier(channel, notifier)

    triggered = await engine.evaluate_conditions("BTCUSDT", {"volume_24h": 2.0})
    assert len(triggered) == 1
    assert calls["count"] == channel_count


# Property 24: Alert Cooldown Enforcement
@given(cooldown=st.floats(min_value=0.1, max_value=120.0, allow_nan=False, allow_infinity=False))
@settings(max_examples=100, deadline=7000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_alert_cooldown_enforcement(cooldown: float) -> None:
    engine = AlertEngine()
    condition = AlertCondition(
        id="c3",
        market_id="BTCUSDT",
        condition_type=ConditionType.PRICE,
        operator=Operator.GT,
        threshold=10.0,
        cooldown_seconds=cooldown,
        channels=["webhook"],
    )
    engine.register_condition(condition)
    engine.register_notifier("webhook", lambda _: _ok())  # type: ignore[arg-type]

    t0 = datetime.now(UTC)
    first = await engine.evaluate_conditions("BTCUSDT", {"mid": 20.0}, now=t0)
    second = await engine.evaluate_conditions(
        "BTCUSDT",
        {"mid": 21.0},
        now=t0 + timedelta(seconds=max(0.0, cooldown * 0.5)),
    )
    third = await engine.evaluate_conditions(
        "BTCUSDT",
        {"mid": 22.0},
        now=t0 + timedelta(seconds=cooldown + 0.1),
    )

    assert len(first) == 1
    assert len(second) == 0
    assert len(third) == 1
