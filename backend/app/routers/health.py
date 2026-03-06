"""Health and metrics endpoints for realtime subsystem."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb
from fastapi import APIRouter, HTTPException, Request, Response

from backend.app.models.config import settings
from backend.app.routers import paper_trading

router = APIRouter()
logger = logging.getLogger(__name__)


def _services(request: Request):
    services = getattr(request.app.state, "realtime_services", None)
    if not services:
        raise HTTPException(status_code=503, detail="Realtime services not initialized")
    return services


def _exchange_health_payload(client) -> dict:
    if client is None:
        return {"status": "degraded", "reason": "exchange client not initialized"}
    try:
        info = client.get_rate_limit_info()
        return {"status": "ok", "exchange": info}
    except Exception as exc:
        logger.warning("Exchange client health check failed: %s", exc)
        return {"status": "degraded", "reason": "exchange client check failed"}


def _time_ago(ts: datetime | None) -> str:
    if ts is None:
        return "n/a"
    now = datetime.now(UTC)
    delta = max((now - ts).total_seconds(), 0.0)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    return f"{int(delta // 86400)} d ago"


def _dataset_health_payload() -> dict[str, Any]:
    parquet_root = Path(settings.data_dir) / "parquet"
    bar_files = list(parquet_root.glob("market_id=*/bars.parquet")) if parquet_root.exists() else []

    total_records = 0
    storage_size_bytes = 0
    datasets: list[dict[str, Any]] = []
    latest_update: datetime | None = None

    for bars_file in bar_files:
        stat = bars_file.stat()
        storage_size_bytes += stat.st_size
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        if latest_update is None or modified > latest_update:
            latest_update = modified

        rows = 0
        try:
            rel = bars_file.relative_to(parquet_root)
            market_id = rel.parent.name.replace("market_id=", "")
            rows_result = duckdb.execute(
                "SELECT COUNT(*) AS n FROM read_parquet(?)",
                [bars_file.as_posix()],
            )
            rows = int(rows_result.fetchone()[0])
            total_records += rows
            datasets.append(
                {
                    "name": market_id,
                    "records": rows,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "last_update": _time_ago(modified),
                    "status": "healthy" if rows > 0 else "warning",
                }
            )
        except Exception:
            datasets.append(
                {
                    "name": bars_file.parent.name.replace("market_id=", ""),
                    "records": rows,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "last_update": _time_ago(modified),
                    "status": "warning",
                }
            )

    datasets.sort(key=lambda item: item["records"], reverse=True)
    total_markets = len(datasets)

    return {
        "total_markets": total_markets,
        "total_records": total_records,
        "storage_size_gb": round(storage_size_bytes / (1024 * 1024 * 1024), 3),
        "last_ingestion": latest_update.isoformat() if latest_update else None,
        "datasets": datasets[:12],
    }


@router.get("/health/connections")
async def get_connections_health(request: Request):
    services = _services(request)
    return services["connection_manager"].get_health_snapshot()["connections"]


@router.get("/health/processing")
async def get_processing_health(request: Request):
    services = _services(request)
    return services["health_monitor"].get_all_metrics()["processing"]


@router.get("/health/memory")
async def get_memory_health(request: Request):
    services = _services(request)
    stats = services["memory_manager"].get_memory_stats()
    return {
        market_id: {
            "candle_count": metric.candle_count,
            "oldest_timestamp": metric.oldest_timestamp.isoformat()
            if metric.oldest_timestamp
            else None,
            "newest_timestamp": metric.newest_timestamp.isoformat()
            if metric.newest_timestamp
            else None,
            "approx_bytes": metric.approx_bytes,
            "tier": metric.tier,
        }
        for market_id, metric in stats.items()
    }


@router.get("/health/rate-limits")
async def get_rate_limit_health(request: Request):
    services = _services(request)
    return {
        client_id: {
            "messages_allowed": stat.messages_allowed,
            "messages_dropped": stat.messages_dropped,
            "dropped_by_type": stat.dropped_by_type,
            "current_tokens": stat.current_tokens,
            "max_tokens": stat.max_tokens,
        }
        for client_id, stat in services["rate_limiter"].get_all_stats().items()
    }


@router.get("/health/config")
async def get_active_config(request: Request):
    services = _services(request)
    config = services["config_manager"].get_system_config()
    return {
        "batch_window_ms": config.batch_window_ms,
        "max_batch_size": config.max_batch_size,
        "max_messages_per_second": config.max_messages_per_second,
        "burst_size": config.burst_size,
        "price_change_threshold": config.price_change_threshold,
        "volume_spike_multiplier": config.volume_spike_multiplier,
        "max_candles_per_market": config.max_candles_per_market,
        "retention_seconds": config.retention_seconds,
        "send_buffer_threshold": config.send_buffer_threshold,
        "slow_client_timeout": config.slow_client_timeout,
        "worker_pool_size": config.worker_pool_size,
        "min_signal_cooldown_seconds": config.min_signal_cooldown_seconds,
        "max_signal_cooldown_seconds": config.max_signal_cooldown_seconds,
    }


@router.get("/cooldown/{market_id}")
async def get_market_cooldown(market_id: str):
    engine = getattr(paper_trading, "_paper_engine", None)
    if not engine:
        raise HTTPException(status_code=404, detail="Paper trading engine not running")
    return {
        "market_id": market_id,
        "cooldown_seconds": engine.get_market_cooldown(market_id),
    }


@router.get("/metrics/tasks")
async def get_task_metrics(request: Request):
    """Get task manager metrics for monitoring.

    Returns:
        Task metrics including current_task_count, queue_depth, and rejected_count
    """
    services = _services(request)
    metrics = services["task_manager"].get_metrics()
    return {
        "current_task_count": metrics.current_task_count,
        "queue_depth": metrics.queue_depth,
        "rejected_count": metrics.rejected_count,
        "completed_count": metrics.completed_count,
        "failed_count": metrics.failed_count,
    }


@router.get("/metrics/prometheus")
async def get_prometheus_metrics(request: Request):
    registry = getattr(request.app.state, "metrics_registry", None)
    if registry is None:
        raise HTTPException(status_code=503, detail="Metrics registry not initialized")
    return Response(content=registry.to_prometheus(), media_type="text/plain; version=0.0.4")


@router.get("/health/exchange-client")
async def get_exchange_client_health(request: Request):
    client = getattr(request.app.state, "exchange_client", None)
    return _exchange_health_payload(client)


@router.get("/health/paper-trading")
async def get_paper_trading_health():
    engine = getattr(paper_trading, "_paper_engine", None)
    if engine is None:
        return {"status": "idle"}
    return {
        "status": "ok" if engine.is_running else "stopped",
        "stats": engine.stats,
        "risk": engine.get_risk_status(),
    }


@router.get("/health/summary")
async def get_health_summary(request: Request):
    """Aggregate high-signal subsystem health into one response."""
    services = _services(request)
    connection_metrics = services["connection_manager"].get_health_snapshot()["connections"]
    processing_metrics = services["health_monitor"].get_all_metrics()["processing"]
    exchange_client = getattr(request.app.state, "exchange_client", None)
    exchange_health = _exchange_health_payload(exchange_client)
    paper_health = await get_paper_trading_health()

    statuses = (
        exchange_health["status"],
        paper_health.get("status", "unknown"),
    )
    acceptable = {"ok", "idle", "stopped"}
    overall = "ok" if all(status in acceptable for status in statuses) else "degraded"

    return {
        "status": overall,
        "connections": connection_metrics,
        "processing": processing_metrics,
        "exchange_client": exchange_health,
        "paper_trading": paper_health,
    }


@router.get("/data/health")
async def get_data_health(request: Request):
    """Data quality and ingestion status for frontend Data page."""
    payload = _dataset_health_payload()
    binance_client = getattr(request.app.state, "binance_client", None)
    ws_connected = bool(binance_client and getattr(binance_client, "is_running", False))

    duckdb_healthy = True
    try:
        duckdb.sql("SELECT 1")
    except Exception:
        duckdb_healthy = False

    parquet_writer_healthy = payload["total_markets"] > 0 or payload["storage_size_gb"] > 0
    rest_api_healthy = True
    quality_components = [
        1.0 if ws_connected else 0.0,
        1.0 if rest_api_healthy else 0.0,
        1.0 if parquet_writer_healthy else 0.0,
        1.0 if duckdb_healthy else 0.0,
    ]
    data_quality_score = round(sum(quality_components) / len(quality_components), 2)

    active_markets = 0
    if binance_client and getattr(binance_client, "markets", None):
        active_markets = sum(
            1 for m in binance_client.markets.values() if getattr(m, "active", False)
        )

    return {
        "total_markets": payload["total_markets"],
        "active_markets": active_markets,
        "total_records": payload["total_records"],
        "storage_size_gb": payload["storage_size_gb"],
        "last_ingestion": payload["last_ingestion"],
        "data_quality_score": data_quality_score,
        "datasets": payload["datasets"],
        "ingestion_status": {
            "ws_connected": ws_connected,
            "rest_api_healthy": rest_api_healthy,
            "parquet_writer_healthy": parquet_writer_healthy,
            "duckdb_healthy": duckdb_healthy,
        },
        "recent_errors": [],
    }
