"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from json import JSONDecodeError
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config_manager import ConfigManager
from backend.app.integrations.coinpaprika_client import CoinPaprikaClient
from backend.app.integrations.discord_notifier import DiscordNotifier, DiscordNotifierConfig
from backend.app.integrations.market_metrics_service import MarketMetricsService
from backend.app.library_integration_config import load_library_integration_config
from backend.app.models.config import SimMode, settings
from backend.app.observability import MetricsRegistry, configure_json_logging
from backend.app.realtime.backpressure_handler import BackpressureHandler
from backend.app.realtime.connection_manager import ConnectionManager
from backend.app.realtime.health_monitor import HealthMonitor
from backend.app.realtime.memory_manager import MemoryManager
from backend.app.realtime.rate_limiter import RateLimiter
from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig
from backend.app.routers import (
    backtest,
    health,
    market,
    models_analytics,
    paper_trading,
    portfolio,
    signals,
    status,
    trades,
)
from backend.app.storage.metrics_store import MetricsStore
from backend.ingest.exchange_client import ExchangeClient, ExchangeConfig, ExchangeType


@dataclass
class AppConfig:
    """Configuration for application initialization.

    Allows dependency injection for testing and custom configurations.
    """
    config_manager: ConfigManager | None = None
    task_manager_config: TaskManagerConfig | None = None
    enable_binance_stream: bool = True
    enable_coinpaprika_metrics: bool = False
    coinpaprika_tracked_coins: list[str] = field(
        default_factory=lambda: ["btc-bitcoin", "eth-ethereum", "sol-solana"]
    )
    cors_origins: list[str] = field(default_factory=lambda: settings.cors_origins)


class AppState:
    """Mutable application state shared via app.state."""

    def __init__(self) -> None:
        self.mode: SimMode = SimMode.BACKTEST
        self.started_at: datetime = datetime.now(UTC)
        self.connected_markets: list[str] = []
        self.is_running: bool = False


async def start_binance_stream(manager: ConnectionManager) -> None:
    """Start Binance stream and broadcast updates to websocket clients."""
    from backend.ingest.binance_client import BinanceClient

    binance_client = BinanceClient()

    async def broadcast_market_update(symbol: str, data: dict):
        if "market" not in data:
            return
        market = data["market"]
        await manager.broadcast(
            {
                "type": "market_update",
                "data": {
                    "symbol": market.symbol,
                    "price": market.price,
                    "change_24h_pct": market.change_24h_pct,
                    "bid": market.bid,
                    "ask": market.ask,
                    "volume_24h": market.volume_24h,
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    binance_client.add_handler(broadcast_market_update)
    await binance_client.start()

    return binance_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Initialize resources on startup
    app_config: AppConfig = app.state.app_config

    library_config = load_library_integration_config()
    if library_config.monitoring.enable_json_logs:
        configure_json_logging()
    app.state.library_integration_config = library_config

    # Initialize config manager
    config_manager = app_config.config_manager or ConfigManager()

    # Initialize realtime services
    rate_limiter = RateLimiter(config_manager.get_rate_limiter_config())
    backpressure_handler = BackpressureHandler(config_manager.get_backpressure_config())
    health_monitor = HealthMonitor()
    memory_manager = MemoryManager(config_manager.get_memory_config())
    manager = ConnectionManager(
        rate_limiter=rate_limiter,
        backpressure_handler=backpressure_handler,
        health_monitor=health_monitor,
    )

    # Initialize task manager within event loop context
    task_manager_config = app_config.task_manager_config or TaskManagerConfig()
    task_manager = BoundedTaskManager(task_manager_config)

    app.state.app_state = getattr(app.state, "app_state", AppState())
    app.state.ws_manager = manager
    app.state.realtime_services = {
        "config_manager": config_manager,
        "rate_limiter": rate_limiter,
        "backpressure_handler": backpressure_handler,
        "health_monitor": health_monitor,
        "memory_manager": memory_manager,
        "connection_manager": manager,
        "task_manager": task_manager,
    }
    app.state.metrics_registry = MetricsRegistry()
    discord_notifier = DiscordNotifier(DiscordNotifierConfig.from_env())
    app.state.discord_notifier = discord_notifier
    exchange_client = None
    try:
        exchange_type = ExchangeType(library_config.exchange.exchange_type)
        exchange_client = ExchangeClient(
            ExchangeConfig(
                exchange_type=exchange_type,
                api_key=library_config.exchange.api_key,
                api_secret=library_config.exchange.api_secret,
                passphrase=library_config.exchange.passphrase,
                enable_rate_limit=library_config.exchange.enable_rate_limit,
                timeout_ms=library_config.exchange.timeout_ms,
                rate_limit=library_config.exchange.rate_limit,
            )
        )
    except (OSError, RuntimeError, ValueError):
        exchange_client = None
    app.state.exchange_client = exchange_client

    coinpaprika_client = None
    market_metrics_task = None
    metrics_store = MetricsStore(f"{settings.data_dir}/metrics.db")
    app.state.metrics_store = metrics_store
    if app_config.enable_coinpaprika_metrics:
        # Initialize CoinPaprika market metrics service
        coinpaprika_client = CoinPaprikaClient()
        market_metrics_service = MarketMetricsService(
            client=coinpaprika_client,
            tracked_coin_ids=app_config.coinpaprika_tracked_coins,
            update_interval_seconds=CoinPaprikaClient.UPDATE_INTERVAL_SECONDS,
            store=metrics_store,
        )
        market_metrics_task = asyncio.create_task(market_metrics_service.run_periodic_updates())
        app.state.market_metrics_service = market_metrics_service

    broadcast_task = asyncio.create_task(broadcast_loop(app))

    # Start Binance stream if enabled
    binance_client = None
    binance_task = None
    if app_config.enable_binance_stream:
        binance_client = await start_binance_stream(manager)
        binance_task = asyncio.create_task(asyncio.sleep(0))  # Placeholder task

    # Store binance client in app state for access by routers
    app.state.binance_client = binance_client

    yield

    # Shutdown task manager gracefully
    await task_manager.shutdown(timeout=5.0)
    if market_metrics_task:
        market_metrics_task.cancel()
    if coinpaprika_client:
        await coinpaprika_client.close()
    if exchange_client is not None:
        await exchange_client.close()
    await discord_notifier.close()
    metrics_store.close()

    broadcast_task.cancel()
    if binance_task:
        binance_task.cancel()

    try:
        if market_metrics_task:
            await market_metrics_task
        await broadcast_task
        if binance_task:
            await binance_task
    except asyncio.CancelledError:
        pass

    if binance_client:
        binance_client.stop()


def create_app(config: AppConfig | None = None) -> FastAPI:
    """Create FastAPI application with optional config override.

    Factory function that creates a configured FastAPI application instance.
    Resources are initialized lazily during the startup event, not at import time.

    Args:
        config: Optional AppConfig for dependency injection. If None, uses defaults.

    Returns:
        Configured FastAPI application instance.

    Example:
        # Production usage
        app = create_app()

        # Testing with custom config
        test_config = AppConfig(enable_binance_stream=False)
        test_app = create_app(test_config)
    """
    if config is None:
        config = AppConfig()

    app = FastAPI(
        title="MarketPy - Crypto Trading Simulator",
        description="AI-powered crypto trading simulator with backtesting and paper trading.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Store config in app state for access during lifespan
    app.state.app_config = config
    app.state.app_state = AppState()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(status.router, prefix="/api", tags=["Status"])
    app.include_router(portfolio.router, prefix="/api", tags=["Portfolio"])
    app.include_router(market.router, prefix="/api", tags=["Market"])
    app.include_router(signals.router, prefix="/api", tags=["Signals"])
    app.include_router(models_analytics.router, prefix="/api", tags=["Models"])
    app.include_router(trades.router, prefix="/api", tags=["Trades"])
    app.include_router(backtest.router, prefix="/api", tags=["Backtest"])
    app.include_router(paper_trading.router, prefix="/api", tags=["Paper Trading"])
    app.include_router(health.router, prefix="/api", tags=["Health"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}

    return app


# Create application instance for production use
app = create_app()


async def broadcast_loop(app: FastAPI):
    """Periodically broadcast live data to all connected clients."""
    manager = app.state.ws_manager
    while True:
        try:
            await asyncio.sleep(2)
            app_state: AppState = app.state.app_state
            message = {
                "type": "status_update",
                "data": {
                    "mode": app_state.mode.value,
                    "is_running": app_state.is_running,
                    "connected_markets_count": len(app_state.connected_markets),
                    "connected_markets": app_state.connected_markets,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                "timestamp": datetime.now(UTC).isoformat(),
            }
            await manager.broadcast(message)
        except (AttributeError, KeyError, RuntimeError):
            await asyncio.sleep(5)


@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """Real-time data push to frontend clients."""
    manager = websocket.app.state.ws_manager
    client_id = str(uuid4())
    await manager.connect(websocket, client_id=client_id)
    try:
        await websocket.send_json(
            {
                "type": "connected",
                "data": {"message": "WebSocket connected successfully", "client_id": client_id},
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
            except JSONDecodeError:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": "Invalid JSON payload"},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            if not isinstance(msg, dict):
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": "Payload must be a JSON object"},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                continue

            if msg.get("type") == "ping":
                await websocket.send_json(
                    {"type": "pong", "timestamp": datetime.now(UTC).isoformat()}
                )
            elif msg.get("type") == "subscribe_market":
                market_id = msg.get("market_id")
                await websocket.send_json(
                    {
                        "type": "subscribed",
                        "data": {"market_id": market_id},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            elif msg.get("type") == "get_status":
                app_state: AppState = websocket.app.state.app_state
                await websocket.send_json(
                    {
                        "type": "status_update",
                        "data": {
                            "mode": app_state.mode.value,
                            "is_running": app_state.is_running,
                            "connected_markets_count": len(app_state.connected_markets),
                        },
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "data": {"message": f"Unsupported message type: {msg.get('type')}"},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
    except WebSocketDisconnect:
        await manager.disconnect(client_id)
    except (AttributeError, KeyError, RuntimeError, ValueError):
        await manager.disconnect(client_id)
