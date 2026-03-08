from __future__ import annotations

from backend.app.openclaw.models import (
    CommandType,
    ConversationMessage,
    ExecutionResult,
    MarketCondition,
    TradingCommand,
    UserContext,
)


def test_trading_command_serialization_round_trip() -> None:
    command = TradingCommand(
        command_type=CommandType.PLACE_ORDER,
        user_id="user-1",
        symbol="btc",
        action="buy",
        quantity=0.1,
        parameters={"market": "spot"},
    )
    payload = command.to_dict()
    restored = TradingCommand.from_dict(payload)
    assert restored.command_type == CommandType.PLACE_ORDER
    assert restored.symbol == "BTC"
    assert restored.action == "buy"
    assert restored.quantity == 0.1


def test_market_condition_price_threshold_evaluation() -> None:
    condition = MarketCondition(
        user_id="user-1",
        condition_type="price_threshold",
        symbol="BTCUSDT",
        parameters={"threshold": 40_000, "direction": "above"},
    )
    assert condition.evaluate({"price": 41_000}) is True
    assert condition.evaluate({"price": 39_000}) is False


def test_user_context_rolling_window() -> None:
    context = UserContext(user_id="user-1")
    for index in range(55):
        context.add_message(
            ConversationMessage(role="user", content=f"message {index}", user_id="user-1"),
            max_messages=50,
        )
    assert len(context.messages) == 50
    assert context.messages[0].content == "message 5"


def test_execution_result_serialization() -> None:
    result = ExecutionResult(success=True, data={"order_id": "abc"}, execution_time_ms=12.3)
    payload = result.to_dict()
    restored = ExecutionResult.from_dict(payload)
    assert restored.success is True
    assert restored.data == {"order_id": "abc"}
