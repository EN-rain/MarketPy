"""Backtest endpoint: execute simulation runs synchronously."""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from secrets import compare_digest
from uuid import uuid4

import pandas as pd
import polars as pl
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from backend.app.backtest.instant_engine import InstantBacktestEngine
from backend.app.models.config import settings
from backend.app.models.market import Candle, MarketInfo
from backend.app.security.input_validation import sanitize_symbol, sanitize_text
from backend.sim.engine import SimEngine
from backend.sim.vectorized_engine import VectorizedBacktestEngine, VectorizedStrategy
from backend.strategies.ai_strategy import AIStrategy
from backend.strategies.mean_reversion import MeanReversionStrategy
from backend.strategies.momentum import MomentumStrategy

router = APIRouter()
logger = logging.getLogger(__name__)

_rate_window: dict[str, deque[datetime]] = defaultdict(deque)
_rate_last_seen: dict[str, datetime] = {}
_rate_checks = 0
_recent_backtests: deque[dict] = deque(maxlen=25)
SUPPORTED_STRATEGIES = ("momentum", "mean_reversion", "ai", "ai_predictor")
SUPPORTED_EXECUTION_MODES = ("event_driven", "vectorized")
MAX_MARKETS_PER_REQUEST = 20


class BacktestRequest(BaseModel):
    market_ids: list[str] = Field(min_length=1, max_length=MAX_MARKETS_PER_REQUEST)
    strategy: str = "momentum"
    start_date: str | None = None
    end_date: str | None = None
    initial_cash: float = 10000.0
    bar_size: str = "5m"
    fill_model: str = "M2"
    fee_rate: float = 0.001
    lookback_bars: int = 12
    momentum_threshold: float = 0.01
    z_entry: float = 2.0
    z_exit: float = 0.5
    edge_buffer: float = 0.02
    use_instant_engine: bool = True
    execution_mode: str = "event_driven"

    @field_validator("strategy")
    @classmethod
    def _sanitize_strategy(cls, value: str) -> str:
        normalized = sanitize_text(value.lower(), max_length=32)
        if normalized not in SUPPORTED_STRATEGIES:
            raise ValueError(f"Unsupported strategy '{value}'")
        return normalized

    @field_validator("market_ids")
    @classmethod
    def _sanitize_market_ids(cls, values: list[str]) -> list[str]:
        cleaned = [sanitize_symbol(item) for item in values]
        if any(not item for item in cleaned):
            raise ValueError("market_ids cannot contain empty symbols")
        return cleaned

    @field_validator("execution_mode")
    @classmethod
    def _sanitize_execution_mode(cls, value: str) -> str:
        normalized = sanitize_text(value.lower(), max_length=32)
        if normalized not in SUPPORTED_EXECUTION_MODES:
            raise ValueError(f"Unsupported execution_mode '{value}'")
        return normalized


class BacktestResult(BaseModel):
    total_pnl: float
    total_pnl_pct: float
    total_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float | None = None
    total_fees: float
    equity_curve: list[dict]
    trades: list[dict]
    diagnostics: dict


def _format_period(start_date: str | None, end_date: str | None) -> str:
    start = start_date[:10] if start_date else "start"
    end = end_date[:10] if end_date else "latest"
    return f"{start} -> {end}"


def _record_recent_backtest(params: BacktestRequest, result: BacktestResult) -> None:
    engine_name = str(result.diagnostics.get("engine", params.execution_mode))
    started_at = datetime.now(UTC).isoformat()
    _recent_backtests.appendleft(
        {
            "id": f"BT-{uuid4().hex[:8].upper()}",
            "strategy": params.strategy,
            "pair": ", ".join(params.market_ids),
            "period": _format_period(params.start_date, params.end_date),
            "markets": params.market_ids,
            "trades": result.total_trades,
            "win_rate": result.win_rate,
            "total_return": result.total_pnl_pct,
            "sharpe": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "status": "completed",
            "duration": result.diagnostics.get("execution_ms"),
            "started_at": started_at,
            "completed_at": started_at,
            "execution_mode": params.execution_mode,
            "engine": engine_name,
        }
    )


def _enforce_backtest_auth_and_rate_limit(request: Request, api_key: str | None) -> None:
    expected = settings.backtest_api_key.strip()
    provided = api_key or ""
    if expected and not compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid API key")

    host = request.client.host if request.client else "unknown"
    now = datetime.now(UTC)
    _prune_rate_limit_state(now)
    one_minute_ago = now.timestamp() - 60
    bucket = _rate_window[host]
    _rate_last_seen[host] = now
    while bucket and bucket[0].timestamp() < one_minute_ago:
        bucket.popleft()
    if len(bucket) >= settings.backtest_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Backtest rate limit exceeded")
    bucket.append(now)


def _prune_rate_limit_state(
    now: datetime,
    stale_seconds: int = 3600,
    max_hosts: int = 2000,
) -> None:
    """Keep per-host rate limiter state bounded in long-running processes."""
    global _rate_checks
    _rate_checks += 1
    if _rate_checks % 100 != 0:
        return

    stale_cutoff = now.timestamp() - stale_seconds
    for host, last_seen in list(_rate_last_seen.items()):
        bucket = _rate_window.get(host)
        if bucket:
            while bucket and bucket[0].timestamp() < now.timestamp() - 60:
                bucket.popleft()
        if last_seen.timestamp() < stale_cutoff:
            _rate_last_seen.pop(host, None)
            _rate_window.pop(host, None)
        elif bucket is not None and len(bucket) == 0:
            _rate_window.pop(host, None)

    if len(_rate_last_seen) <= max_hosts:
        return

    overflow = len(_rate_last_seen) - max_hosts
    oldest_hosts = sorted(_rate_last_seen.items(), key=lambda item: item[1])[:overflow]
    for host, _ in oldest_hosts:
        _rate_last_seen.pop(host, None)
        _rate_window.pop(host, None)


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {value}") from exc


def _load_candles_for_market(
    market_id: str,
    start_dt: datetime | None,
    end_dt: datetime | None,
) -> list[Candle]:
    parquet_path = Path(settings.data_dir) / "parquet" / f"market_id={market_id}" / "bars.parquet"
    if not parquet_path.exists():
        raise HTTPException(status_code=404, detail=f"No bar data for market_id={market_id}")

    df = _read_parquet_cached(str(parquet_path), parquet_path.stat().st_mtime_ns).clone()
    if start_dt:
        df = df.filter(pl.col("timestamp") >= pl.lit(start_dt))
    if end_dt:
        df = df.filter(pl.col("timestamp") <= pl.lit(end_dt))
    if df.is_empty():
        raise HTTPException(status_code=400, detail=f"No data in requested range for {market_id}")

    candles: list[Candle] = []
    for row in df.iter_rows(named=True):
        bid = row.get("bid")
        ask = row.get("ask")
        mid = row.get("mid")
        if bid is None or ask is None:
            if mid is None:
                continue
            bid = float(mid)
            ask = float(mid)
        if mid is None:
            mid = (float(bid) + float(ask)) / 2

        candles.append(
            Candle(
                timestamp=row["timestamp"],
                open=float(row.get("open", mid)),
                high=float(row.get("high", mid)),
                low=float(row.get("low", mid)),
                close=float(row.get("close", mid)),
                mid=float(mid),
                bid=float(bid),
                ask=float(ask),
                spread=float(row.get("spread", float(ask) - float(bid))),
                volume=float(row.get("volume", 0.0)),
                trade_count=int(row.get("trade_count", 0)),
            )
        )
    return candles


@lru_cache(maxsize=64)
def _read_parquet_cached(path: str, mtime_ns: int) -> pl.DataFrame:
    _ = mtime_ns  # cache invalidation key
    return pl.read_parquet(path)


def _build_strategy(request: BacktestRequest):
    if request.strategy == "momentum":
        return MomentumStrategy(
            lookback=request.lookback_bars,
            threshold=request.momentum_threshold,
            order_size=100.0,
        )
    if request.strategy == "mean_reversion":
        return MeanReversionStrategy(
            lookback=request.lookback_bars,
            z_entry=request.z_entry,
            z_exit=request.z_exit,
            order_size=100.0,
        )
    if request.strategy in {"ai", "ai_predictor"}:
        return AIStrategy(edge_buffer=request.edge_buffer)
    raise HTTPException(status_code=400, detail=f"Unsupported strategy '{request.strategy}'")


class _MomentumVectorizedStrategy(VectorizedStrategy):
    def __init__(self, lookback: int, threshold: float) -> None:
        self.lookback = lookback
        self.threshold = threshold

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = data.copy()
        frame["momentum"] = frame["close"].pct_change(self.lookback)
        frame["entries"] = frame["momentum"] > self.threshold
        frame["exits"] = frame["momentum"] < 0
        return frame


class _MeanReversionVectorizedStrategy(VectorizedStrategy):
    def __init__(self, lookback: int, z_entry: float, z_exit: float) -> None:
        self.lookback = lookback
        self.z_entry = z_entry
        self.z_exit = z_exit

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = data.copy()
        mean = frame["close"].rolling(self.lookback).mean()
        std = frame["close"].rolling(self.lookback).std()
        zscore = (frame["close"] - mean) / std.replace(0, pd.NA)
        frame["entries"] = zscore < -self.z_entry
        frame["exits"] = zscore > -self.z_exit
        return frame


class _AIVectorizedStrategy(VectorizedStrategy):
    def __init__(self, edge_buffer: float) -> None:
        self.edge_buffer = edge_buffer

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        frame = data.copy()
        ret = frame["close"].pct_change().fillna(0.0)
        frame["entries"] = ret > self.edge_buffer
        frame["exits"] = ret < -self.edge_buffer
        return frame


def _build_vectorized_strategy(request: BacktestRequest) -> VectorizedStrategy:
    if request.strategy == "momentum":
        return _MomentumVectorizedStrategy(
            lookback=request.lookback_bars,
            threshold=request.momentum_threshold,
        )
    if request.strategy == "mean_reversion":
        return _MeanReversionVectorizedStrategy(
            lookback=request.lookback_bars,
            z_entry=request.z_entry,
            z_exit=request.z_exit,
        )
    if request.strategy in {"ai", "ai_predictor"}:
        return _AIVectorizedStrategy(edge_buffer=request.edge_buffer)
    raise HTTPException(status_code=400, detail=f"Unsupported strategy '{request.strategy}'")


@router.post("/backtest/run", response_model=BacktestResult)
async def run_backtest(
    request: Request,
    params: BacktestRequest,
    x_api_key: str | None = Header(default=None),
):
    """Run a backtest and return deterministic summary metrics."""
    _enforce_backtest_auth_and_rate_limit(request, x_api_key)

    start_dt = _parse_ts(params.start_date)
    end_dt = _parse_ts(params.end_date)
    if start_dt and end_dt and end_dt < start_dt:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    if params.execution_mode == "vectorized":
        if len(params.market_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail="Vectorized mode currently supports a single market per request",
            )
        market_id = params.market_ids[0]
        candles = _load_candles_for_market(market_id, start_dt=start_dt, end_dt=end_dt)
        frame = pd.DataFrame(
            [
                {
                    "timestamp": candle.timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                }
                for candle in candles
            ]
        ).set_index("timestamp")
        strategy = _build_vectorized_strategy(params)
        engine = VectorizedBacktestEngine(
            initial_cash=params.initial_cash,
            fee_rate=params.fee_rate,
            slippage=0.0,
        )
        result = engine.run(strategy=strategy, data=frame)
        payload = BacktestResult(
            total_pnl=result.total_return * params.initial_cash,
            total_pnl_pct=result.total_return * 100.0,
            total_trades=len(result.trades),
            win_rate=result.win_rate,
            max_drawdown=result.max_drawdown,
            sharpe_ratio=result.sharpe_ratio,
            total_fees=0.0,
            equity_curve=[
                {
                    "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                    "cash": None,
                    "positions_value": None,
                    "total_equity": float(value),
                    "drawdown": None,
                }
                for ts, value in result.equity_curve.items()
            ],
            trades=result.trades.to_dict(orient="records"),
            diagnostics={
                "engine": "vectorized",
                "execution_mode": result.execution_mode.value,
                "profit_factor": result.profit_factor,
            },
        )
        _record_recent_backtest(params, payload)
        return payload

    if params.use_instant_engine:
        try:
            instant_engine = InstantBacktestEngine(data_dir=settings.data_dir)
            instant_result = instant_engine.run_backtest(
                strategy=params.strategy,
                symbols=params.market_ids,
                timeframe=params.bar_size,
                start_date=start_dt,
                end_date=end_dt,
                lookback_bars=params.lookback_bars,
                momentum_threshold=params.momentum_threshold,
            )
            payload = BacktestResult(
                total_pnl=instant_result.total_return * params.initial_cash,
                total_pnl_pct=instant_result.total_return * 100.0,
                total_trades=len(instant_result.trades),
                win_rate=instant_result.win_rate,
                max_drawdown=instant_result.max_drawdown,
                sharpe_ratio=instant_result.sharpe_ratio,
                total_fees=0.0,
                equity_curve=instant_result.equity_curve,
                trades=[
                    {
                        "id": idx,
                        "timestamp": trade.timestamp.isoformat(),
                        "market_id": trade.symbol,
                        "action": trade.side,
                        "price": trade.price,
                        "size": trade.size,
                        "fee": 0.0,
                        "strategy": params.strategy,
                        "edge": None,
                        "pnl": None,
                    }
                    for idx, trade in enumerate(instant_result.trades, start=1)
                ],
                diagnostics={
                    "execution_ms": instant_result.execution_ms,
                    "engine": "instant",
                    "markets_processed": len(params.market_ids),
                },
            )
            _record_recent_backtest(params, payload)
            return payload
        except Exception as exc:
            logger.warning(
                "Instant backtest failed, falling back to event-driven engine: %s",
                exc,
            )
            # Fallback to legacy engine when instant mode cannot run for this request.
            pass

    engine = SimEngine()
    engine.config.initial_cash = params.initial_cash
    engine.config.default_fee_rate = params.fee_rate
    engine.config.fill_model = params.fill_model

    for market_id in params.market_ids:
        candles = _load_candles_for_market(market_id, start_dt=start_dt, end_dt=end_dt)
        info = MarketInfo(
            condition_id=market_id,
            question=f"Market {market_id}",
            token_id_yes=market_id,
            active=True,
        )
        engine.add_market(info, candles)

    strategy = _build_strategy(params)
    result = engine.run(strategy)
    portfolio = result.portfolio

    returns: list[float] = []
    curve = portfolio.equity_curve
    for i in range(1, len(curve)):
        prev = curve[i - 1].total_equity
        curr = curve[i].total_equity
        if prev > 0:
            returns.append((curr - prev) / prev)
    sharpe = None
    if returns:
        avg = sum(returns) / len(returns)
        variance = sum((r - avg) ** 2 for r in returns) / len(returns)
        std = variance**0.5
        if std > 0:
            sharpe = avg / std

    payload = BacktestResult(
        total_pnl=portfolio.total_pnl,
        total_pnl_pct=portfolio.total_pnl_pct,
        total_trades=len(portfolio.trades),
        win_rate=portfolio.win_rate,
        max_drawdown=portfolio.max_drawdown,
        sharpe_ratio=sharpe,
        total_fees=portfolio.total_fees_paid,
        equity_curve=[
            {
                "timestamp": pt.timestamp.isoformat(),
                "cash": pt.cash,
                "positions_value": pt.positions_value,
                "total_equity": pt.total_equity,
                "drawdown": pt.drawdown,
            }
            for pt in portfolio.equity_curve
        ],
        trades=[
            {
                "id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "market_id": t.market_id,
                "action": t.action.value,
                "price": t.price,
                "size": t.size,
                "fee": t.fee,
                "strategy": t.strategy,
                "edge": t.edge,
                "pnl": t.pnl,
            }
            for t in portfolio.trades
        ],
        diagnostics={
            "duration_bars": result.duration_bars,
            "markets_processed": result.markets_processed,
            "orders_submitted": result.orders_submitted,
            "orders_filled": result.orders_filled,
            "errors": result.errors,
        },
    )
    _record_recent_backtest(params, payload)
    return payload


@router.get("/backtest/capabilities")
async def get_backtest_capabilities():
    """Describe supported strategy and execution options for backtest requests."""
    return {
        "strategies": list(SUPPORTED_STRATEGIES),
        "execution_modes": list(SUPPORTED_EXECUTION_MODES),
        "defaults": {
            "strategy": "momentum",
            "execution_mode": "event_driven",
            "bar_size": "5m",
            "fill_model": "M2",
            "use_instant_engine": True,
        },
        "constraints": {
            "vectorized_single_market_only": True,
            "api_key_required": bool(settings.backtest_api_key.strip()),
            "rate_limit_per_minute": settings.backtest_rate_limit_per_minute,
            "max_markets_per_request": MAX_MARKETS_PER_REQUEST,
        },
    }


@router.get("/backtest/rate-limit-status")
async def get_backtest_rate_limit_status(request: Request):
    """Inspect current host backtest rate-limit usage without consuming quota."""
    host = request.client.host if request.client else "unknown"
    now = datetime.now(UTC)
    _prune_rate_limit_state(now)
    bucket = _rate_window.get(host, deque())
    one_minute_ago = now.timestamp() - 60
    while bucket and bucket[0].timestamp() < one_minute_ago:
        bucket.popleft()
    used = len(bucket)
    limit = settings.backtest_rate_limit_per_minute
    return {
        "host": host,
        "used": used,
        "limit": limit,
        "remaining": max(limit - used, 0),
        "window_seconds": 60,
    }


@router.get("/backtest/recent")
async def get_recent_backtests():
    """Return recent completed backtests for the terminal UI."""
    return {"items": list(_recent_backtests)}
