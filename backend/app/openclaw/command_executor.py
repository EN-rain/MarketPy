"""Command execution layer translating parsed intents to MarketPy API calls."""

from __future__ import annotations

import hmac
import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

import httpx

from .config import OpenClawConfig, RiskLimitSettings
from .discord_bridge import DiscordBridge
from .logging import StructuredLogger
from .models import CommandType, ExecutionResult, TradingCommand


@dataclass(slots=True)
class PortfolioState:
    equity: float = 0.0
    daily_pnl_pct: float = 0.0
    open_positions: int = 0
    max_position_pct: float = 0.0


class MarketPyApiClient:
    """HTTP wrapper over existing MarketPy APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: int = 30,
        logger: StructuredLogger | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        signing_secret: str | None = None,
    ):
        self._logger = logger or StructuredLogger("openclaw.marketpy_client")
        self._signing_secret = signing_secret or ""
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=timeout_seconds,
            transport=transport,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _signed_headers(self, payload: dict[str, Any]) -> dict[str, str]:
        if not self._signing_secret:
            return {}
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        signature = hmac.new(self._signing_secret.encode("utf-8"), body, sha256).hexdigest()
        return {"X-OpenClaw-Signature": signature}

    async def get_price(self, symbol: str) -> dict[str, Any]:
        response = await self._client.get(f"/api/market/{symbol.upper()}")
        response.raise_for_status()
        return response.json()

    async def place_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = self._signed_headers(payload)
        response = await self._client.post(
            "/api/paper-trading/order", json=payload, headers=headers
        )
        response.raise_for_status()
        return response.json()

    async def get_positions(self, user_id: str) -> dict[str, Any]:
        response = await self._client.get("/api/portfolio", params={"user_id": user_id})
        response.raise_for_status()
        return response.json()

    async def run_backtest(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = self._signed_headers(payload)
        response = await self._client.post("/api/backtest/run", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()


class RiskValidator:
    """Validates commands against configured risk constraints."""

    def __init__(self, settings: RiskLimitSettings):
        self._settings = settings
        self._last_trade_by_user: dict[str, datetime] = {}

    def validate(
        self,
        command: TradingCommand,
        *,
        portfolio_state: PortfolioState,
    ) -> tuple[bool, str | None]:
        if command.command_type != CommandType.PLACE_ORDER:
            return True, None

        now = datetime.now(UTC)
        last_trade = self._last_trade_by_user.get(command.user_id)
        if last_trade is not None:
            elapsed = (now - last_trade).total_seconds()
            if elapsed < self._settings.min_trade_interval_seconds:
                return False, "Minimum trade interval has not elapsed"

        if portfolio_state.open_positions >= self._settings.max_open_positions:
            return False, "Maximum open positions exceeded"

        if portfolio_state.daily_pnl_pct <= -abs(self._settings.max_daily_loss_pct):
            return False, "Daily loss threshold exceeded"

        if portfolio_state.max_position_pct > self._settings.max_position_size_pct:
            return False, "Position size limit exceeded"

        if command.quantity and command.quantity > self._settings.max_order_size:
            return False, "Order size exceeds max_order_size"

        self._last_trade_by_user[command.user_id] = now
        return True, None


class CommandExecutor:
    """Routes and executes validated commands against MarketPy services."""

    def __init__(
        self,
        config: OpenClawConfig,
        *,
        logger: StructuredLogger | None = None,
        discord_bridge: DiscordBridge | None = None,
        api_client: MarketPyApiClient | None = None,
        risk_validator: RiskValidator | None = None,
    ):
        self._logger = logger or StructuredLogger("openclaw.command_executor")
        self._discord = discord_bridge
        self._api_client = api_client or MarketPyApiClient(
            base_url=config.marketpy_base_url,
            timeout_seconds=config.performance.command_timeout_seconds,
            logger=self._logger,
            signing_secret=config.security.signing_secret
            if config.security.enable_request_signing
            else "",
        )
        self._risk_validator = risk_validator or RiskValidator(config.risk_limits)
        self._last_execution_ms: dict[str, float] = {}

    async def close(self) -> None:
        await self._api_client.close()

    @property
    def last_execution_ms(self) -> dict[str, float]:
        return dict(self._last_execution_ms)

    async def execute(
        self,
        command: TradingCommand,
        *,
        portfolio_state: PortfolioState | None = None,
        discord_channel_id: str | None = None,
    ) -> ExecutionResult:
        start = time.perf_counter()
        portfolio = portfolio_state or PortfolioState()

        try:
            if command.command_type == CommandType.PLACE_ORDER:
                valid, reason = self._risk_validator.validate(command, portfolio_state=portfolio)
                if not valid:
                    return await self._finish(
                        command=command,
                        success=False,
                        data=None,
                        error=reason,
                        started_at=start,
                        discord_channel_id=discord_channel_id,
                    )

            result = await self._dispatch(command)
            return await self._finish(
                command=command,
                success=True,
                data=result,
                error=None,
                started_at=start,
                discord_channel_id=discord_channel_id,
            )
        except Exception as exc:
            return await self._finish(
                command=command,
                success=False,
                data=None,
                error=str(exc),
                started_at=start,
                discord_channel_id=discord_channel_id,
            )

    async def _dispatch(self, command: TradingCommand) -> dict[str, Any]:
        command_type = command.command_type
        if command_type == CommandType.PRICE_CHECK:
            if not command.symbol:
                raise ValueError("Missing symbol for price check")
            return await self._api_client.get_price(command.symbol)

        if command_type == CommandType.PLACE_ORDER:
            if not command.symbol or not command.action or command.quantity is None:
                raise ValueError("Order requires symbol, action, and quantity")
            payload = {
                "market_id": command.symbol,
                "side": command.action,
                "size": self._sanitize_number(command.quantity),
            }
            payload.update(command.parameters)
            return await self._api_client.place_order(payload)

        if command_type == CommandType.POSITION_QUERY:
            return await self._api_client.get_positions(command.user_id)

        if command_type == CommandType.RUN_BACKTEST:
            payload = dict(command.parameters)
            payload.setdefault("strategy_name", command.parameters.get("strategy_name", "default"))
            if command.symbol:
                payload.setdefault("market_id", command.symbol)
            return await self._api_client.run_backtest(payload)

        if command_type == CommandType.MARKET_ANALYSIS:
            if not command.symbol:
                raise ValueError("Missing symbol for market analysis")
            return await self._api_client.get_price(command.symbol)

        raise ValueError(f"Unsupported command type: {command_type}")

    async def _finish(
        self,
        *,
        command: TradingCommand,
        success: bool,
        data: dict[str, Any] | None,
        error: str | None,
        started_at: float,
        discord_channel_id: str | None,
    ) -> ExecutionResult:
        execution_ms = (time.perf_counter() - started_at) * 1000.0
        self._last_execution_ms[command.command_type] = execution_ms
        result = ExecutionResult(
            success=success,
            data=data,
            error=error,
            execution_time_ms=execution_ms,
            correlation_id=command.correlation_id,
        )
        self._logger.info(
            "Command executed",
            {
                "command_type": command.command_type,
                "success": success,
                "execution_time_ms": round(execution_ms, 2),
                "error": error,
            },
        )
        if self._discord and discord_channel_id:
            embed = self._discord.create_embed(
                title="Command Executed" if success else "Command Failed",
                description=f"{command.command_type} for {command.user_id}",
                fields={
                    "success": success,
                    "execution_time_ms": round(execution_ms, 2),
                    "error": error or "",
                },
            )
            await self._discord.send_message(
                discord_channel_id,
                "✅ Command executed" if success else "❌ Command failed",
                embeds=[embed],
                reactions=["✅"] if success else ["❌"],
            )
        return result

    @staticmethod
    def _sanitize_number(value: float) -> float:
        if value != value:  # NaN check
            raise ValueError("Invalid numeric value: NaN")
        if value == float("inf") or value == float("-inf"):
            raise ValueError("Invalid numeric value: infinity")
        return float(value)
