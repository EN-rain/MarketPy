"""Unified exchange connectivity built around ccxt.

This module provides an async-friendly adapter with:
- multi-exchange support (Binance/Coinbase/Kraken)
- retry with exponential backoff
- structured API call logging
- in-memory metrics for latency/call/error tracking
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from backend.app.models.market import Candle, OrderBookSnapshot

logger = logging.getLogger(__name__)

try:
    import ccxt.async_support as ccxt_async  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    ccxt_async = None  # type: ignore[assignment]


class ExchangeType(str, Enum):
    BINANCE = "binance"
    COINBASE = "coinbase"
    KRAKEN = "kraken"


@dataclass(slots=True)
class ExchangeConfig:
    exchange_type: ExchangeType = ExchangeType.BINANCE
    api_key: str | None = None
    api_secret: str | None = None
    passphrase: str | None = None
    enable_rate_limit: bool = True
    rate_limit: int = 1200
    timeout_ms: int = 30000
    max_retries: int = 3
    backoff_base_seconds: float = 1.0

    @classmethod
    def from_env(cls, exchange_type: ExchangeType = ExchangeType.BINANCE) -> ExchangeConfig:
        prefix = exchange_type.value.upper()
        return cls(
            exchange_type=exchange_type,
            api_key=os.getenv(f"{prefix}_API_KEY"),
            api_secret=os.getenv(f"{prefix}_API_SECRET"),
            passphrase=os.getenv(f"{prefix}_PASSPHRASE"),
            enable_rate_limit=os.getenv("EXCHANGE_ENABLE_RATE_LIMIT", "true").lower() in {
                "1",
                "true",
                "yes",
                "on",
            },
            rate_limit=int(os.getenv("EXCHANGE_RATE_LIMIT", "1200")),
            timeout_ms=int(os.getenv("EXCHANGE_TIMEOUT_MS", "30000")),
            max_retries=int(os.getenv("EXCHANGE_MAX_RETRIES", "3")),
            backoff_base_seconds=float(os.getenv("EXCHANGE_BACKOFF_BASE_SECONDS", "1.0")),
        )


@dataclass(slots=True)
class APICallMetric:
    count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.count if self.count else 0.0

    @property
    def error_rate(self) -> float:
        return self.error_count / self.count if self.count else 0.0


@dataclass(slots=True)
class ExchangeMetrics:
    by_endpoint: dict[str, APICallMetric] = field(default_factory=lambda: defaultdict(APICallMetric))

    def record(self, endpoint: str, latency_ms: float, ok: bool) -> None:
        metric = self.by_endpoint[endpoint]
        metric.count += 1
        metric.total_latency_ms += latency_ms
        if not ok:
            metric.error_count += 1

    def snapshot(self) -> dict[str, dict[str, float | int]]:
        return {
            endpoint: {
                "count": metric.count,
                "error_count": metric.error_count,
                "avg_latency_ms": metric.avg_latency_ms,
                "error_rate": metric.error_rate,
            }
            for endpoint, metric in self.by_endpoint.items()
        }


class ExchangeClient:
    """Unified exchange client that wraps ccxt async exchange adapters."""

    def __init__(
        self,
        config: ExchangeConfig,
        exchange_factory: Callable[[ExchangeConfig], Any] | None = None,
    ) -> None:
        self.config = config
        self._exchange = exchange_factory(config) if exchange_factory else self._build_exchange(config)
        self._metrics = ExchangeMetrics()

    @property
    def exchange_id(self) -> str:
        return self.config.exchange_type.value

    @property
    def metrics(self) -> dict[str, dict[str, float | int]]:
        return self._metrics.snapshot()

    def _build_exchange(self, config: ExchangeConfig) -> Any:
        if ccxt_async is None:
            raise RuntimeError(
                "ccxt async support is not installed. Install dependency 'ccxt' to enable ExchangeClient."
            )

        exchange_cls = getattr(ccxt_async, config.exchange_type.value, None)
        if exchange_cls is None:
            raise ValueError(f"Unsupported exchange type: {config.exchange_type.value}")

        kwargs: dict[str, Any] = {
            "enableRateLimit": config.enable_rate_limit,
            "timeout": config.timeout_ms,
            "rateLimit": config.rate_limit,
        }
        if config.api_key:
            kwargs["apiKey"] = config.api_key
        if config.api_secret:
            kwargs["secret"] = config.api_secret
        if config.passphrase:
            kwargs["password"] = config.passphrase

        return exchange_cls(kwargs)

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        text = symbol.strip().upper()
        if "/" in text:
            return text
        suffixes = ("USDT", "USDC", "BUSD", "USD", "BTC", "ETH", "EUR")
        for suffix in suffixes:
            if text.endswith(suffix) and len(text) > len(suffix):
                base = text[: -len(suffix)]
                return f"{base}/{suffix}"
        return text

    @staticmethod
    def _to_candle(ohlcv: list[Any]) -> Candle:
        ts_ms, open_, high, low, close, volume = ohlcv[:6]
        ts = datetime.fromtimestamp(float(ts_ms) / 1000, UTC)
        mid = (float(open_) + float(close)) / 2.0
        return Candle(
            timestamp=ts,
            open=float(open_),
            high=float(high),
            low=float(low),
            close=float(close),
            mid=mid,
            bid=float(close),
            ask=float(close),
            spread=0.0,
            volume=float(volume),
            trade_count=0,
        )

    @staticmethod
    def _to_orderbook(symbol: str, payload: dict[str, Any]) -> OrderBookSnapshot:
        bids_raw = payload.get("bids") or []
        asks_raw = payload.get("asks") or []
        best_bid = float(bids_raw[0][0]) if bids_raw else None
        best_ask = float(asks_raw[0][0]) if asks_raw else None
        mid = None
        spread = None
        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2.0
            spread = best_ask - best_bid

        timestamp_ms = payload.get("timestamp")
        ts = (
            datetime.fromtimestamp(float(timestamp_ms) / 1000, UTC)
            if timestamp_ms is not None
            else datetime.now(UTC)
        )
        return OrderBookSnapshot(
            token_id=symbol,
            timestamp=ts,
            best_bid=best_bid,
            best_ask=best_ask,
            mid=mid,
            spread=spread,
            bids=[(float(p), float(s)) for p, s in bids_raw],
            asks=[(float(p), float(s)) for p, s in asks_raw],
        )

    def _log_api_call(
        self,
        *,
        endpoint: str,
        symbol: str | None,
        status: str,
        duration_ms: float,
        correlation_id: str,
        error: str | None = None,
    ) -> None:
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "exchange": self.exchange_id,
            "endpoint": endpoint,
            "symbol": symbol,
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "correlation_id": correlation_id,
        }
        if error is not None:
            entry["error"] = error
        logger.info(json.dumps(entry, separators=(",", ":"), ensure_ascii=True))

    async def _call_with_retry(
        self,
        endpoint: str,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        symbol: str | None = None,
        **kwargs: Any,
    ) -> Any:
        delay = self.config.backoff_base_seconds
        last_exc: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            correlation_id = str(uuid4())
            started = time.perf_counter()
            try:
                payload = await func(*args, **kwargs)
                elapsed_ms = (time.perf_counter() - started) * 1000
                self._metrics.record(endpoint, elapsed_ms, ok=True)
                self._log_api_call(
                    endpoint=endpoint,
                    symbol=symbol,
                    status="ok",
                    duration_ms=elapsed_ms,
                    correlation_id=correlation_id,
                )
                return payload
            except Exception as exc:  # pragma: no cover - network/ccxt dependent
                last_exc = exc
                elapsed_ms = (time.perf_counter() - started) * 1000
                self._metrics.record(endpoint, elapsed_ms, ok=False)
                self._log_api_call(
                    endpoint=endpoint,
                    symbol=symbol,
                    status="error",
                    duration_ms=elapsed_ms,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                if attempt >= self.config.max_retries:
                    break
                await asyncio.sleep(delay)
                delay *= 2.0

        if last_exc is None:
            raise RuntimeError(f"{endpoint} failed without exception details")
        raise last_exc

    async def fetch_ohlcv(
        self,
        symbol: str,
        timeframe: str = "1h",
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[Candle]:
        normalized = self._normalize_symbol(symbol)
        since_ms = int(since.timestamp() * 1000) if since else None
        remaining = max(1, limit)
        cursor = since_ms
        candles: list[Candle] = []

        while remaining > 0:
            batch_size = min(remaining, 1000)
            rows = await self._call_with_retry(
                "fetch_ohlcv",
                self._exchange.fetch_ohlcv,
                normalized,
                timeframe,
                cursor,
                batch_size,
                symbol=normalized,
            )
            if not rows:
                break

            converted = [self._to_candle(row) for row in rows]
            candles.extend(converted)
            remaining -= len(converted)

            if len(rows) < batch_size:
                break

            last_ts_ms = int(rows[-1][0])
            cursor = last_ts_ms + 1

        candles.sort(key=lambda c: c.timestamp)
        return candles[:limit]

    async def fetch_order_book(self, symbol: str, limit: int = 20) -> OrderBookSnapshot:
        normalized = self._normalize_symbol(symbol)
        payload = await self._call_with_retry(
            "fetch_order_book",
            self._exchange.fetch_order_book,
            normalized,
            limit,
            symbol=normalized,
        )
        return self._to_orderbook(symbol=normalized, payload=payload)

    async def fetch_ticker(self, symbol: str) -> dict[str, Any]:
        normalized = self._normalize_symbol(symbol)
        payload = await self._call_with_retry(
            "fetch_ticker",
            self._exchange.fetch_ticker,
            normalized,
            symbol=normalized,
        )
        return dict(payload)

    async def fetch_trades(
        self,
        symbol: str,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized = self._normalize_symbol(symbol)
        since_ms = int(since.timestamp() * 1000) if since else None
        rows = await self._call_with_retry(
            "fetch_trades",
            self._exchange.fetch_trades,
            normalized,
            since_ms,
            limit,
            symbol=normalized,
        )
        return [dict(row) for row in rows]

    async def fetch_server_time(self) -> datetime:
        ts_ms = await self._call_with_retry("fetch_time", self._exchange.fetch_time)
        return datetime.fromtimestamp(float(ts_ms) / 1000, UTC)

    async def get_server_time(self) -> datetime:
        return await self.fetch_server_time()

    def get_rate_limit_info(self) -> dict[str, Any]:
        return {
            "exchange": self.exchange_id,
            "enable_rate_limit": self.config.enable_rate_limit,
            "rate_limit": self.config.rate_limit,
            "timeout_ms": self.config.timeout_ms,
        }

    def get_websocket_url(self, channels: list[str]) -> str:
        if self.config.exchange_type == ExchangeType.BINANCE:
            joined = "/".join(channels)
            return f"wss://stream.binance.com:9443/stream?streams={joined}"
        raise NotImplementedError(
            f"WebSocket URL builder not implemented for exchange {self.config.exchange_type.value}"
        )

    async def close(self) -> None:
        if self._exchange is not None:
            close_fn = getattr(self._exchange, "close", None)
            if close_fn is not None:
                await close_fn()
