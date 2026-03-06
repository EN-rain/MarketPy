"""Main OpenClaw autonomous agent orchestration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from backend.ingest.exchange_client import ExchangeClient

from .command_executor import CommandExecutor, PortfolioState
from .config import OpenClawConfig, OpenClawConfigManager
from .context_manager import ContextManager
from .discord_bridge import DiscordBridge, DiscordMessage
from .kimi_k2_client import KimiK2Client
from .logging import StructuredLogger, configure_structured_logging
from .market_monitor import MarketMonitor
from .metrics import OpenClawMetrics
from .nlp import NaturalLanguageProcessor
from .portfolio_optimizer import PortfolioOptimizer
from .risk_advisor import RiskAdvisor
from .skill_system import SkillExtensionSystem
from .strategy_assistant import StrategyAssistant


class _ExchangeAdapter:
    """Adapter converting ExchangeClient output to monitor-friendly structures."""

    def __init__(self, exchange_client: ExchangeClient):
        self._client = exchange_client

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        return await self._client.fetch_ticker(symbol)

    async def fetch_ohlcv(
        self, symbol: str, timeframe: str = "1h", limit: int = 120
    ) -> list[list[Any]]:
        candles = await self._client.fetch_ohlcv(symbol=symbol, timeframe=timeframe, limit=limit)
        rows: list[list[Any]] = []
        for candle in candles:
            rows.append(
                [
                    int(candle.timestamp.timestamp() * 1000),
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                ]
            )
        return rows


@dataclass(slots=True)
class QueuedCommand:
    message: DiscordMessage
    created_at: datetime


class AutonomousAgent:
    """Coordinates all OpenClaw components and background services."""

    def __init__(
        self,
        *,
        config_manager: OpenClawConfigManager | None = None,
        exchange_client: ExchangeClient | None = None,
        logger: StructuredLogger | None = None,
    ):
        self.config_manager = config_manager or OpenClawConfigManager()
        self.config: OpenClawConfig = self.config_manager.config

        configure_structured_logging(
            level=self._parse_log_level(self.config.log_level),
            log_file=self.config.log_file,
        )
        self.logger = logger or StructuredLogger("openclaw.autonomous_agent")
        self.metrics = OpenClawMetrics()

        self.context_manager = ContextManager(
            data_dir=self.config.data_dir,
            max_messages=50,
            backup_interval_seconds=self.config.monitoring.context_backup_interval_seconds,
            encryption_key=self.config.security.context_encryption_key or None,
        )
        self.kimi_client = KimiK2Client(self.config.kimi_k2)
        self.discord_bridge = DiscordBridge(self.config.discord)
        self.command_executor = CommandExecutor(
            self.config,
            discord_bridge=self.discord_bridge,
        )
        self.nlp = NaturalLanguageProcessor(self.kimi_client, self.context_manager)
        self.exchange_client = exchange_client
        self.market_monitor: MarketMonitor | None = None
        self.strategy_assistant = StrategyAssistant(
            kimi_client=self.kimi_client,
            command_executor=self.command_executor,
        )
        self.risk_advisor = RiskAdvisor(
            self.config.risk_limits,
            discord_bridge=self.discord_bridge,
            monitor_interval_seconds=self.config.monitoring.risk_monitor_interval_seconds,
        )
        self.portfolio_optimizer = PortfolioOptimizer()
        self.skill_system = SkillExtensionSystem(
            self.config.skills_dir,
            kimi_client=self.kimi_client,
        )

        self._command_queue: asyncio.Queue[QueuedCommand] = asyncio.Queue(
            maxsize=self.config.performance.max_queue_size
        )
        self._workers: list[asyncio.Task[None]] = []
        self._running = False
        self._started_at = datetime.now(UTC)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._started_at = datetime.now(UTC)
        self.metrics.increment("openclaw_start_total")

        self.skill_system.load_all()
        await self.context_manager.load_contexts_from_disk()
        await self.context_manager.start_backup_loop()
        self.discord_bridge.register_command_handler(self._handle_discord_command)
        await self.discord_bridge.start()

        if self.exchange_client:
            adapter = _ExchangeAdapter(self.exchange_client)
            self.market_monitor = MarketMonitor(
                exchange_client=adapter,
                command_executor=self.command_executor,
                discord_bridge=self.discord_bridge,
                monitor_interval_seconds=self.config.monitoring.market_monitor_interval_seconds,
            )
            await self.market_monitor.start()

        await self.risk_advisor.start()

        worker_count = min(
            self.config.performance.max_concurrent_users,
            max(1, self.config.kimi_k2.max_concurrent_calls),
        )
        for idx in range(worker_count):
            self._workers.append(asyncio.create_task(self._worker_loop(worker_id=idx)))
        self.logger.info("OpenClaw autonomous agent started", {"workers": worker_count})

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False

        for worker in self._workers:
            worker.cancel()
        for worker in self._workers:
            try:
                await worker
            except asyncio.CancelledError:
                pass
        self._workers.clear()

        await self.risk_advisor.stop()
        if self.market_monitor:
            await self.market_monitor.stop()
        await self.context_manager.stop_backup_loop()
        await self.discord_bridge.stop()
        await self.command_executor.close()
        await self.kimi_client.close()
        self.logger.info("OpenClaw autonomous agent stopped")

    async def enqueue_message(self, message: DiscordMessage) -> None:
        if not self._running:
            raise RuntimeError("Autonomous agent is not running")
        self.metrics.set_gauge("openclaw_queue_depth", float(self._command_queue.qsize()))
        await self._command_queue.put(QueuedCommand(message=message, created_at=datetime.now(UTC)))

    async def _handle_discord_command(self, message: DiscordMessage) -> str | dict[str, Any]:
        await self.enqueue_message(message)
        return {
            "content": "⌛ Command queued for execution.",
            "embeds": [
                self.discord_bridge.create_embed(
                    title="Command Received",
                    description=f"Queued command from {message.user_id}",
                    fields={"queue_depth": self._command_queue.qsize()},
                )
            ],
        }

    async def _worker_loop(self, worker_id: int) -> None:
        while True:
            try:
                queued = await self._command_queue.get()
                self.metrics.set_gauge("openclaw_queue_depth", float(self._command_queue.qsize()))
                with self.metrics.timer("openclaw_command_duration_seconds"):
                    command = await self.nlp.parse_command(
                        queued.message.content, queued.message.user_id
                    )
                    result = await self.command_executor.execute(
                        command,
                        portfolio_state=PortfolioState(),
                        discord_channel_id=queued.message.channel_id,
                    )
                    if result.success:
                        self.metrics.increment("openclaw_commands_total")
                    else:
                        self.metrics.increment("openclaw_command_errors_total")
                self._command_queue.task_done()
                self.logger.info(
                    "Command processed",
                    {
                        "worker_id": worker_id,
                        "user_id": queued.message.user_id,
                        "success": result.success,
                    },
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.metrics.increment("openclaw_worker_errors_total")
                self.logger.exception(
                    "Worker loop error", {"worker_id": worker_id, "error": str(exc)}
                )
                await self._notify_admin_error(str(exc))

    async def _notify_admin_error(self, error: str) -> None:
        channel = self.config.discord.admin_channel
        if not channel:
            return
        await self.discord_bridge.send_message(
            channel,
            f"🚨 OpenClaw critical error: {error}",
        )

    def health_check(self) -> dict[str, Any]:
        uptime_seconds = int((datetime.now(UTC) - self._started_at).total_seconds())
        return {
            "status": "healthy" if self._running else "stopped",
            "components": {
                "discord_bridge": "running" if self._running else "stopped",
                "kimi_k2_client": "running" if self._running else "stopped",
                "context_manager": "running" if self._running else "stopped",
                "market_monitor": "running" if self.market_monitor else "disabled",
                "risk_advisor": "running" if self._running else "stopped",
                "command_queue_depth": self._command_queue.qsize(),
            },
            "uptime_seconds": uptime_seconds,
            "metrics": self.metrics.snapshot(),
        }

    def metrics_text(self) -> str:
        return self.metrics.to_prometheus()

    @staticmethod
    def _parse_log_level(level_name: str) -> int:
        import logging

        return getattr(logging, level_name.upper(), logging.INFO)
