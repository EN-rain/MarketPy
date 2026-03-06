"""Natural language processing layer for OpenClaw trading commands."""

from __future__ import annotations

import re
from typing import Any

from .context_manager import ContextManager
from .kimi_k2_client import KimiK2Client
from .logging import StructuredLogger
from .models import CommandType, MarketCondition, TradingCommand

_SYMBOL_RE = re.compile(r"\b([A-Z]{2,10})(?:USDT|USD|USDC)?\b", re.IGNORECASE)
_QUANTITY_RE = re.compile(r"\b(\d+(?:\.\d+)?)\b")
_RSI_RE = re.compile(r"rsi\s*(<=|>=|<|>)\s*(\d+(?:\.\d+)?)", re.IGNORECASE)


def _sanitize_message(text: str) -> str:
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return sanitized.strip()[:1000]


class NaturalLanguageProcessor:
    """Parses natural-language user input into `TradingCommand` objects."""

    def __init__(
        self,
        kimi_client: KimiK2Client,
        context_manager: ContextManager,
        *,
        logger: StructuredLogger | None = None,
    ):
        self._kimi_client = kimi_client
        self._context_manager = context_manager
        self._logger = logger or StructuredLogger("openclaw.nlp")

    async def parse_command(
        self,
        message: str,
        user_id: str,
    ) -> TradingCommand:
        clean_message = _sanitize_message(message)
        await self._context_manager.add_message(user_id, "user", clean_message)
        context = await self._context_manager.get_context(user_id)
        context_messages = [
            {"role": item.role, "content": item.content} for item in context.messages[-10:]
        ]

        try:
            intent = await self._kimi_client.extract_intent(clean_message, context_messages)
        except Exception as exc:
            self._logger.warning(
                "Kimi K2 intent extraction failed, using fallback parser",
                {"error": str(exc), "user_id": user_id},
            )
            intent = self._fallback_parse(clean_message)

        command = self._intent_to_command(intent, user_id=user_id)
        errors = command.validate()
        if errors:
            missing = self._missing_required(command)
            if missing:
                clarification = self.request_clarification(missing)
                command = TradingCommand(
                    command_type=CommandType.CLARIFICATION,
                    user_id=user_id,
                    parameters={"missing": missing, "clarification": clarification},
                )
            self._logger.warning(
                "Command validation failed",
                {"errors": errors, "user_id": user_id, "intent": intent},
            )

        await self._context_manager.add_message(
            user_id, "assistant", f"parsed:{command.command_type}"
        )
        self._logger.info(
            "Command parsed",
            {"user_id": user_id, "command_type": command.command_type, "symbol": command.symbol},
        )
        return command

    def request_clarification(self, missing_params: list[str]) -> str:
        return (
            "I need more details before I can execute this command. "
            f"Missing fields: {', '.join(missing_params)}."
        )

    def validate_parameters(self, command: TradingCommand) -> tuple[bool, list[str]]:
        errors = command.validate()
        return not errors, errors

    def _missing_required(self, command: TradingCommand) -> list[str]:
        missing: list[str] = []
        for field_name in command.required_params():
            value = getattr(command, field_name, None)
            if value in (None, "", []):
                missing.append(field_name)
        return missing

    def _intent_to_command(self, intent: dict[str, Any], user_id: str) -> TradingCommand:
        command_type = str(intent.get("command_type", CommandType.UNKNOWN))
        symbol = intent.get("symbol")
        if isinstance(symbol, str):
            symbol = symbol.upper()

        conditions: list[MarketCondition] = []
        intent_conditions = intent.get("conditions") or []
        if isinstance(intent_conditions, list):
            for raw in intent_conditions:
                if isinstance(raw, dict):
                    conditions.append(MarketCondition.from_dict({"user_id": user_id, **raw}))

        quantity = intent.get("quantity")
        if quantity is not None:
            try:
                quantity = float(quantity)
            except (TypeError, ValueError):
                quantity = None

        action = intent.get("action")
        if isinstance(action, str):
            action = action.lower()

        return TradingCommand(
            command_type=command_type,
            user_id=user_id,
            symbol=symbol,
            action=action,
            quantity=quantity,
            conditions=conditions,
            parameters=dict(intent.get("parameters", {})),
        )

    def _fallback_parse(self, message: str) -> dict[str, Any]:
        lowered = message.lower()
        symbol_match = _SYMBOL_RE.search(message)
        symbol = symbol_match.group(1).upper() if symbol_match else None
        quantity_match = _QUANTITY_RE.search(message)
        quantity = float(quantity_match.group(1)) if quantity_match else None

        if "price" in lowered or lowered.startswith("check"):
            return {"command_type": CommandType.PRICE_CHECK, "symbol": symbol, "parameters": {}}

        if lowered.startswith("buy") or " buy " in lowered:
            return {
                "command_type": CommandType.PLACE_ORDER,
                "symbol": symbol,
                "action": "buy",
                "quantity": quantity,
                "parameters": {},
            }

        if lowered.startswith("sell") or " sell " in lowered:
            return {
                "command_type": CommandType.PLACE_ORDER,
                "symbol": symbol,
                "action": "sell",
                "quantity": quantity,
                "parameters": {},
            }

        if "position" in lowered:
            return {"command_type": CommandType.POSITION_QUERY, "symbol": symbol, "parameters": {}}

        if "backtest" in lowered:
            return {
                "command_type": CommandType.RUN_BACKTEST,
                "symbol": symbol,
                "parameters": {"strategy_name": "default_strategy"},
            }

        if "analy" in lowered:
            return {"command_type": CommandType.MARKET_ANALYSIS, "symbol": symbol, "parameters": {}}

        if "if rsi" in lowered:
            rsi_match = _RSI_RE.search(message)
            threshold = float(rsi_match.group(2)) if rsi_match else 30.0
            direction = "below" if rsi_match and rsi_match.group(1) in {"<", "<="} else "above"
            return {
                "command_type": CommandType.CONDITION_ADD,
                "symbol": symbol,
                "conditions": [
                    {
                        "condition_type": "rsi_level",
                        "symbol": symbol,
                        "parameters": {"level": threshold, "direction": direction},
                    }
                ],
                "parameters": {},
            }

        return {"command_type": CommandType.UNKNOWN, "parameters": {}}
