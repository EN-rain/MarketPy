"""Automation execution engine with risk controls and kill switch."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from .models import ActionLogEntry, ActionStatus, ActionType, AutomatedAction

Executor = Callable[[AutomatedAction], Awaitable[dict[str, Any]]]
ErrorNotifier = Callable[[str], Awaitable[bool]]


class KillSwitch:
    """Global gate that can halt all automated execution."""

    def __init__(self) -> None:
        self._engaged = False
        self.reason: str | None = None

    @property
    def engaged(self) -> bool:
        return self._engaged

    def engage(self, reason: str) -> None:
        self._engaged = True
        self.reason = reason

    def reset(self) -> None:
        self._engaged = False
        self.reason = None


class AutomationEngine:
    """Executes automated actions with risk validation and failure containment."""

    def __init__(self, error_notifier: ErrorNotifier | None = None) -> None:
        self.kill_switch = KillSwitch()
        self.executors: dict[ActionType, Executor] = {}
        self.action_log: list[ActionLogEntry] = []
        self._halted_on_error = False
        self._error_notifier = error_notifier

    def register_executor(self, action_type: ActionType, executor: Executor) -> None:
        self.executors[action_type] = executor

    def validate_risk_limits(
        self,
        action: AutomatedAction,
        portfolio_state: Mapping[str, float | int | None] | None = None,
    ) -> tuple[bool, str]:
        state = portfolio_state or {}
        market_list = action.risk_limits.allowed_markets
        if market_list and action.market_id not in market_list:
            return False, "market_not_allowed"

        daily_pnl = float(state.get("daily_pnl", 0.0) or 0.0)
        if daily_pnl <= -abs(action.risk_limits.max_daily_loss):
            return False, "daily_loss_limit_exceeded"

        if action.action_type == ActionType.PLACE_ORDER:
            price = float(action.parameters.get("price", 0.0) or 0.0)
            size = float(action.parameters.get("size", 0.0) or 0.0)
            order_notional = abs(price * size)
            if order_notional > action.risk_limits.max_order_notional:
                return False, "order_notional_limit_exceeded"

            current_position = float(state.get("position_notional", 0.0) or 0.0)
            projected = abs(current_position) + order_notional
            if projected > action.risk_limits.max_position_notional:
                return False, "position_notional_limit_exceeded"

        return True, "ok"

    async def execute_action(
        self,
        action: AutomatedAction,
        portfolio_state: Mapping[str, float | int | None] | None = None,
    ) -> dict[str, Any]:
        if self.kill_switch.engaged:
            return self._log_and_result(action, ActionStatus.SKIPPED, "kill_switch_engaged")
        if self._halted_on_error:
            return self._log_and_result(action, ActionStatus.SKIPPED, "halted_after_error")

        valid, reason = self.validate_risk_limits(action, portfolio_state)
        if not valid:
            return self._log_and_result(action, ActionStatus.REJECTED, reason)

        executor = self.executors.get(action.action_type)
        if executor is None:
            return await self._handle_error(action, "executor_not_registered")

        try:
            payload = await executor(action)
        except Exception as exc:
            return await self._handle_error(action, f"execution_error:{exc}")

        result = self._log_and_result(action, ActionStatus.SUCCESS, "executed")
        result["payload"] = payload
        return result

    async def _handle_error(self, action: AutomatedAction, reason: str) -> dict[str, Any]:
        self._halted_on_error = True
        self.kill_switch.engage(reason)
        message = (
            "automation failure "
            f"action_id={action.id} type={action.action_type.value} reason={reason}"
        )
        await self._send_error_notification(
            message
        )
        return self._log_and_result(action, ActionStatus.FAILED, reason)

    async def _send_error_notification(self, message: str) -> None:
        if self._error_notifier is None:
            return
        await self._error_notifier(message)

    def _log_and_result(
        self, action: AutomatedAction, status: ActionStatus, message: str
    ) -> dict[str, Any]:
        now = datetime.now(UTC)
        entry = ActionLogEntry(
            action_id=action.id,
            action_type=action.action_type,
            market_id=action.market_id,
            status=status,
            message=message,
            timestamp=now,
        )
        self.action_log.append(entry)
        return {
            "action_id": action.id,
            "status": status.value,
            "message": message,
            "timestamp": now.isoformat(),
        }
