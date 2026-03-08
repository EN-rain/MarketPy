"""FastAPI application entry point."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from json import JSONDecodeError
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from backend.app.config_manager import ConfigManager
from backend.app.integrations.coinpaprika_client import CoinPaprikaClient
from backend.app.integrations.discord_notifier import DiscordNotifier, DiscordNotifierConfig
from backend.app.integrations.market_metrics_service import MarketMetricsService
from backend.app.library_integration_config import load_library_integration_config
from backend.app.models.config import SimMode, settings
from backend.app.observability import MetricsRegistry, configure_json_logging
from backend.app.realtime.backpressure_handler import BackpressureHandler
from backend.app.realtime.connection_manager import ConnectionManager
from backend.app.realtime.distributed_state import build_subscription_store
from backend.app.realtime.health_monitor import HealthMonitor
from backend.app.realtime.memory_manager import MemoryManager
from backend.app.realtime.rate_limiter import RateLimiter
from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig
from backend.app.routers import (
    backtest,
    health,
    market,
    monitoring,
    models_analytics,
    paper_trading,
    portfolio,
    security,
    signals,
    status,
    trades,
)
from backend.app.security.auth import APIKeyStore, JWTManager, get_current_user
from backend.app.security.monitoring import SecurityMonitor
from backend.app.security.rate_limit import HttpRateLimiter, RateLimitMiddleware
from backend.app.storage.metrics_store import MetricsStore
from backend.ingest.exchange_client import ExchangeClient, ExchangeConfig, ExchangeType
from backend.monitoring.alerts import AlertManager, AlertRule
from backend.monitoring.dashboard import MonitoringDashboard
from backend.monitoring.metrics import MetricsCollector


@dataclass
class AppConfig:
    """Configuration for application initialization.

    Allows dependency injection for testing and custom configurations.
    """
    config_manager: ConfigManager | None = None
    task_manager_config: TaskManagerConfig | None = None
    enable_binance_stream: bool = True
    enable_prediction_autostart: bool = False
    enable_coinpaprika_metrics: bool = False
    default_prediction_markets: list[str] = field(
        default_factory=lambda: ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    )
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


async def start_binance_stream(
    manager: ConnectionManager,
) -> tuple[object, asyncio.Task[None]]:
    """Start Binance stream in the background and return the client plus task."""
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
    stream_task = asyncio.create_task(binance_client.start())
    return binance_client, stream_task


def validate_model_artifacts(model_dir: str | Path | None = None) -> list[Path]:
    """Ensure trained model artifacts exist before enabling live predictions."""
    resolved_dir = Path(model_dir or settings.model_dir)
    artifacts = sorted(resolved_dir.glob("*.joblib")) if resolved_dir.exists() else []
    if not artifacts:
        raise RuntimeError(
            "No trained model artifacts found in models/ directory. "
            "Run training pipeline or provide default models."
        )
    return artifacts


async def auto_start_prediction_service(app: FastAPI, market_ids: list[str]) -> None:
    """Create and start the default paper trading engine for live predictions."""
    from backend.app.routers.paper_trading import set_binance_handler, set_paper_engine
    from backend.paper_trading.engine import PaperTradingEngine
    from backend.paper_trading.live_feed import LiveFeedUpdate
    from backend.strategies.ai_strategy import AIStrategy

    ws_manager = app.state.ws_manager
    binance_client = app.state.binance_client
    notifier = getattr(app.state, "discord_notifier", None)

    paper_engine = PaperTradingEngine(
        initial_cash=10000.0,
        fill_model="M2",
        fee_rate=settings.default_fee_rate,
        discord_notifier=notifier,
    )
    strategy = AIStrategy(edge_buffer=0.0, kelly_fraction=0.05, order_size=0.1)
    paper_engine.add_strategy(strategy)

    async def broadcast_to_ui(event_type: str, data: dict) -> None:
        await ws_manager.broadcast(
            {
                "type": f"paper_{event_type}",
                "data": data,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

    paper_engine.add_ui_handler(broadcast_to_ui)

    normalized_markets = [market_id.upper().strip() for market_id in market_ids if market_id.strip()]
    normalized_market_set = set(normalized_markets)
    for market_id in normalized_markets:
        paper_engine.register_market(market_id, {"question": market_id.replace("USDT", "")})

    async def handle_binance_update(symbol: str, data: dict) -> None:
        if "market" not in data:
            return
        market = data["market"]
        if normalized_market_set and market.symbol.upper() not in normalized_market_set:
            return

        update = LiveFeedUpdate(
            market_id=market.symbol.upper(),
            timestamp=market.last_update,
            event_type="price_change",
            data={"price": market.price, "change_24h": market.change_24h},
            bid=market.bid,
            ask=market.ask,
            mid=market.price,
            spread=market.spread,
            last_trade=market.price,
        )
        await paper_engine.on_market_update(update)

    binance_client.add_handler(handle_binance_update)
    set_binance_handler(handle_binance_update)
    set_paper_engine(paper_engine)
    app.state.paper_engine = paper_engine
    app.state.app_state.mode = SimMode.PAPER
    app.state.app_state.is_running = True
    app.state.app_state.connected_markets = normalized_markets
    paper_engine.start()

    if normalized_markets:
        await paper_engine._notify_ui(
            "signal",
            {
                "market_id": normalized_markets[0],
                "decision": "HOLD",
                "confidence": 0.0,
                "edge": 0.0,
                "edge_pct": 0.0,
                "current_mid": None,
                "predicted_price": None,
                "reason": "Prediction engine auto-started. Waiting for live market ticks.",
                "strategy": getattr(strategy, "name", strategy.__class__.__name__),
            },
        )


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
    app.state.app_settings = settings
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
    app.state.ws_channel_subscriptions = {}
    app.state.ws_subscription_store = build_subscription_store()
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
    metrics_collector = MetricsCollector()
    alert_manager = AlertManager()
    alert_manager.add_rule(AlertRule("drawdown_critical", "drawdown", ">", 0.15, "critical"))
    alert_manager.add_rule(AlertRule("drift_warning", "drift_alerts", ">", 0.0, "warning"))
    app.state.monitoring_dashboard = MonitoringDashboard(
        metrics_collector=metrics_collector,
        alert_manager=alert_manager,
    )
    app.state.jwt_manager = JWTManager(
        secret=settings.security_jwt_secret,
        exp_minutes=settings.security_jwt_exp_minutes,
    )
    app.state.api_key_store = APIKeyStore(
        encryption_key=settings.security_api_key_encryption_key
    )
    app.state.security_monitor = SecurityMonitor(
        failed_auth_threshold=settings.security_failed_auth_block_threshold,
        block_duration_seconds=settings.security_block_duration_seconds,
    )

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
    prediction_task = None

    if app_config.enable_binance_stream and app_config.enable_prediction_autostart:
        app.state.model_artifacts = [
            str(path) for path in validate_model_artifacts()
        ]

    # Start Binance stream if enabled
    binance_client = None
    binance_task = None
    if app_config.enable_binance_stream:
        binance_client, binance_task = await start_binance_stream(manager)

    # Store binance client in app state for access by routers
    app.state.binance_client = binance_client
    app.state.paper_engine = None

    if app_config.enable_binance_stream and app_config.enable_prediction_autostart:
        prediction_task = asyncio.create_task(
            auto_start_prediction_service(app, app_config.default_prediction_markets)
        )

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
    if prediction_task:
        prediction_task.cancel()
    if binance_task:
        binance_task.cancel()

    try:
        if market_metrics_task:
            await market_metrics_task
        await broadcast_task
        if prediction_task:
            await prediction_task
        if binance_task:
            await binance_task
    except asyncio.CancelledError:
        pass

    if binance_client:
        binance_client.stop()
    if getattr(app.state, "paper_engine", None) is not None:
        app.state.paper_engine.stop()


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
    app.state.app_settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    if settings.security_enable_rate_limit:
        app.add_middleware(
            RateLimitMiddleware,
            limiter=HttpRateLimiter(
                rate_per_sec=settings.security_rate_limit_rps,
                burst_size=settings.security_rate_limit_burst,
            ),
        )

    app.include_router(status.router, prefix="/api", tags=["Status"])
    app.include_router(portfolio.router, prefix="/api", tags=["Portfolio"])
    app.include_router(market.router, prefix="/api", tags=["Market"])
    app.include_router(signals.router, prefix="/api", tags=["Signals"])
    app.include_router(monitoring.router, prefix="/api", tags=["Monitoring"])
    app.include_router(models_analytics.router, prefix="/api", tags=["Models"])
    app.include_router(trades.router, prefix="/api", tags=["Trades"])
    app.include_router(backtest.router, prefix="/api", tags=["Backtest"])
    app.include_router(paper_trading.router, prefix="/api", tags=["Paper Trading"])
    app.include_router(security.router, prefix="/api", tags=["Security"])
    app.include_router(health.router, prefix="/api", tags=["Health"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok", "timestamp": datetime.now(UTC).isoformat()}

    @app.middleware("http")
    async def security_guard(request, call_next):
        ip = request.client.host if request.client else "unknown"
        monitor = getattr(request.app.state, "security_monitor", None)
        if monitor is not None:
            monitor.record_request(ip=ip, endpoint=f"{request.method} {request.url.path}")
            if monitor.is_blocked(ip):
                return JSONResponse(status_code=403, content={"detail": "IP temporarily blocked"})
            if monitor.suspicious_usage(ip):
                return JSONResponse(status_code=429, content={"detail": "Suspicious API usage detected"})

        if settings.security_require_https:
            forwarded_proto = request.headers.get("x-forwarded-proto", "")
            if request.url.scheme != "https" and forwarded_proto.lower() != "https":
                https_url = str(request.url.replace(scheme="https"))
                return RedirectResponse(url=https_url, status_code=307)

        if settings.security_enable_auth and request.url.path.startswith("/api"):
            allowed_paths = {
                "/api/status",
                "/api/health",
                "/api/backtest/capabilities",
                "/api/security/token",
            }
            if request.url.path not in allowed_paths:
                try:
                    get_current_user(request)
                except Exception as exc:
                    if monitor is not None:
                        monitor.record_auth_attempt(ip=ip, user_id="anonymous", success=False)
                    if isinstance(exc, HTTPException):
                        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
                    return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        if settings.security_require_https:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains; preload",
            )
        return response

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
            status_message = {
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
            await manager.broadcast(status_message)
            await broadcast_channel_updates(app)
        except (AttributeError, KeyError, RuntimeError):
            await asyncio.sleep(5)


async def broadcast_channel_updates(app: FastAPI) -> None:
    manager = app.state.ws_manager
    subscriptions: dict[str, set[str]] = app.state.ws_channel_subscriptions
    subscription_store = getattr(app.state, "ws_subscription_store", None)
    dashboard_payload = app.state.monitoring_dashboard.payload()
    timestamp = datetime.now(UTC).isoformat()
    channel_payloads: dict[str, dict[str, object]] = {
        "predictions": {
            "type": "predictions_update",
            "data": {
                "symbol": "BTCUSDT",
                "prediction": dashboard_payload["dashboard_panels"]["explainability"]["prediction"],
                "shap_values": dashboard_payload["dashboard_panels"]["explainability"]["top_shap"],
            },
            "timestamp": timestamp,
        },
        "risk": {
            "type": "risk_update",
            "data": dashboard_payload["dashboard_panels"]["risk_dashboard"],
            "timestamp": timestamp,
        },
        "execution": {
            "type": "execution_update",
            "data": dashboard_payload["dashboard_panels"]["execution_quality"],
            "timestamp": timestamp,
        },
        "alerts": {
            "type": "alerts_update",
            "data": {"items": dashboard_payload["active_alerts"]},
            "timestamp": timestamp,
        },
    }
    for client_id in manager.active_client_ids:
        if subscription_store is not None:
            channels = subscription_store.get_channels(client_id)
        else:
            channels = subscriptions.get(client_id, set())
        for channel in channels:
            payload = channel_payloads.get(channel)
            if payload is not None:
                await manager.send_to_client(client_id, payload, message_type=f"channel_{channel}")


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
            elif msg.get("type") == "subscribe_channels":
                channels_raw = msg.get("channels", [])
                allowed_channels = {"predictions", "risk", "execution", "alerts"}
                channels = {
                    str(channel).strip().lower()
                    for channel in channels_raw
                    if str(channel).strip().lower() in allowed_channels
                }
                websocket.app.state.ws_channel_subscriptions[client_id] = channels
                subscription_store = getattr(websocket.app.state, "ws_subscription_store", None)
                if subscription_store is not None:
                    subscription_store.set_channels(client_id, channels)
                await websocket.send_json(
                    {
                        "type": "subscribed_channels",
                        "data": {"channels": sorted(channels)},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
            elif msg.get("type") == "unsubscribe_channels":
                channels_raw = msg.get("channels", [])
                remove = {str(channel).strip().lower() for channel in channels_raw}
                existing = websocket.app.state.ws_channel_subscriptions.get(client_id, set())
                remaining = {channel for channel in existing if channel not in remove}
                websocket.app.state.ws_channel_subscriptions[client_id] = remaining
                subscription_store = getattr(websocket.app.state, "ws_subscription_store", None)
                if subscription_store is not None:
                    remaining = subscription_store.remove_channels(client_id, remove)
                await websocket.send_json(
                    {
                        "type": "unsubscribed_channels",
                        "data": {"channels": sorted(remove), "remaining": sorted(remaining)},
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
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
        websocket.app.state.ws_channel_subscriptions.pop(client_id, None)
        subscription_store = getattr(websocket.app.state, "ws_subscription_store", None)
        if subscription_store is not None:
            subscription_store.clear_client(client_id)
        await manager.disconnect(client_id)
    except (AttributeError, KeyError, RuntimeError, ValueError):
        websocket.app.state.ws_channel_subscriptions.pop(client_id, None)
        subscription_store = getattr(websocket.app.state, "ws_subscription_store", None)
        if subscription_store is not None:
            subscription_store.clear_client(client_id)
        await manager.disconnect(client_id)
