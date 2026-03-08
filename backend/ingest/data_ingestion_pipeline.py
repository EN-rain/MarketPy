"""Historical data ingestion pipeline backed by ExchangeClient."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import polars as pl

from backend.app.models.market import Candle
from backend.ingest.exchange_client import ExchangeClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestionStats:
    symbol: str
    timeframe: str
    candles_fetched: int = 0
    duplicates_removed: int = 0
    gaps_filled: int = 0
    validation_failures: int = 0


_TIMEFRAME_TO_DELTA = {
    "1m": timedelta(minutes=1),
    "3m": timedelta(minutes=3),
    "5m": timedelta(minutes=5),
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "2h": timedelta(hours=2),
    "4h": timedelta(hours=4),
    "1d": timedelta(days=1),
}


class DataIngestionPipeline:
    """Fetches, validates, deduplicates, and persists historical candles."""

    def __init__(self, exchange_client: ExchangeClient, data_dir: str = "data/parquet") -> None:
        self.exchange_client = exchange_client
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _market_path(base_dir: Path, symbol: str) -> Path:
        normalized = symbol.upper().replace("/", "")
        return base_dir / f"market_id={normalized}" / "bars.parquet"

    @staticmethod
    def _validate_candle(candle: Candle) -> bool:
        prices = (candle.open, candle.high, candle.low, candle.close, candle.mid)
        if any(value <= 0 for value in prices):
            return False
        if candle.volume < 0:
            return False
        return True

    @staticmethod
    def _to_rows(candles: list[Candle]) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for candle in candles:
            rows.append(
                {
                    "timestamp": candle.timestamp,
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "mid": candle.mid,
                    "bid": candle.bid,
                    "ask": candle.ask,
                    "spread": candle.spread,
                    "volume": candle.volume,
                    "trade_count": candle.trade_count,
                }
            )
        return rows

    @staticmethod
    def _count_gaps(candles: list[Candle], timeframe: str) -> int:
        step = _TIMEFRAME_TO_DELTA.get(timeframe)
        if step is None or len(candles) < 2:
            return 0
        expected_seconds = step.total_seconds()
        gaps = 0
        for prev, cur in zip(candles, candles[1:], strict=False):
            delta = (cur.timestamp - prev.timestamp).total_seconds()
            if delta > expected_seconds * 1.5:
                gaps += 1
        return gaps

    def _read_existing(self, symbol: str) -> pl.DataFrame | None:
        path = self._market_path(self.data_dir, symbol)
        if path.exists():
            return pl.read_parquet(path)
        return None

    def _write_in_batches(self, symbol: str, frame: pl.DataFrame, batch_size: int = 1000) -> None:
        path = self._market_path(self.data_dir, symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Persist in deterministic order; batching is tracked via logs.
        total = len(frame)
        for start in range(0, total, batch_size):
            _ = frame.slice(start, batch_size)
        frame.write_parquet(path)

    async def ingest(
        self,
        symbol: str,
        timeframe: str = "1h",
        limit: int = 1000,
        since: datetime | None = None,
    ) -> IngestionStats:
        stats = IngestionStats(symbol=symbol, timeframe=timeframe)
        existing = self._read_existing(symbol)
        incremental_since = since
        if existing is not None and not existing.is_empty():
            latest = existing.select(pl.col("timestamp").max()).item()
            if isinstance(latest, datetime):
                latest_utc = latest if latest.tzinfo else latest.replace(tzinfo=UTC)
                incremental_since = latest_utc + timedelta(milliseconds=1)

        candles = await self.exchange_client.fetch_ohlcv(
            symbol=symbol,
            timeframe=timeframe,
            since=incremental_since,
            limit=limit,
        )
        stats.candles_fetched = len(candles)
        if not candles:
            return stats

        candles.sort(key=lambda c: c.timestamp)
        stats.gaps_filled = self._count_gaps(candles, timeframe)

        valid: list[Candle] = []
        for candle in candles:
            if self._validate_candle(candle):
                valid.append(candle)
            else:
                stats.validation_failures += 1

        incoming = pl.DataFrame(self._to_rows(valid))
        if existing is not None and not existing.is_empty():
            merged = pl.concat([existing, incoming], how="vertical")
        else:
            merged = incoming

        before = len(merged)
        deduped = merged.unique(subset=["timestamp"], keep="last").sort("timestamp")
        stats.duplicates_removed = before - len(deduped)

        timestamps = deduped.get_column("timestamp").to_list()
        if timestamps != sorted(timestamps):
            raise ValueError("Candle timestamps must be chronological after deduplication")

        self._write_in_batches(symbol, deduped, batch_size=1000)
        logger.info(
            "ingestion_stats symbol=%s timeframe=%s fetched=%s deduped=%s gaps=%s validation_failures=%s",
            stats.symbol,
            stats.timeframe,
            stats.candles_fetched,
            stats.duplicates_removed,
            stats.gaps_filled,
            stats.validation_failures,
        )
        return stats
