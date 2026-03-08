"""Execution analysis for filled orders."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import time


@dataclass(frozen=True, slots=True)
class ExecutionAnalysisRecord:
    order_id: str
    symbol: str
    predicted_price: float
    order_price: float
    execution_price: float
    slippage_bps: float
    execution_time_ms: float
    timestamp: datetime


class ExecutionAnalyzer:
    """Analyzes fills and persists execution records."""

    def __init__(self, db_path: str | Path = "data/execution_analysis.sqlite") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_analysis (
                order_id TEXT PRIMARY KEY,
                symbol TEXT NOT NULL,
                predicted_price REAL NOT NULL,
                order_price REAL NOT NULL,
                execution_price REAL NOT NULL,
                slippage_bps REAL NOT NULL,
                execution_time_ms REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_analysis_symbol_time
            ON execution_analysis (symbol, timestamp DESC)
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_execution_analysis_timestamp
            ON execution_analysis (timestamp DESC)
            """
        )
        self._conn.commit()
        self._query_cache: dict[str, tuple[float, list[ExecutionAnalysisRecord]]] = {}
        self._query_cache_ttl_seconds = 1.0

    @staticmethod
    def compute_slippage_bps(predicted_price: float, execution_price: float) -> float:
        if predicted_price == 0:
            return 0.0
        return float(((execution_price - predicted_price) / predicted_price) * 10_000.0)

    def analyze_execution(
        self,
        *,
        order_id: str,
        symbol: str,
        predicted_price: float,
        order_price: float,
        execution_price: float,
        execution_time_ms: float,
        timestamp: datetime | None = None,
    ) -> ExecutionAnalysisRecord:
        ts = timestamp or datetime.now(UTC)
        record = ExecutionAnalysisRecord(
            order_id=order_id,
            symbol=symbol,
            predicted_price=float(predicted_price),
            order_price=float(order_price),
            execution_price=float(execution_price),
            slippage_bps=self.compute_slippage_bps(predicted_price, execution_price),
            execution_time_ms=float(execution_time_ms),
            timestamp=ts,
        )
        self._conn.execute(
            """
            INSERT OR REPLACE INTO execution_analysis
            (order_id, symbol, predicted_price, order_price, execution_price, slippage_bps, execution_time_ms, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.order_id,
                record.symbol,
                record.predicted_price,
                record.order_price,
                record.execution_price,
                record.slippage_bps,
                record.execution_time_ms,
                record.timestamp.isoformat(),
            ),
        )
        self._conn.commit()
        self._query_cache.clear()
        return record

    def _cached_query(self, key: str, query: str, params: tuple[object, ...]) -> list[ExecutionAnalysisRecord]:
        cached = self._query_cache.get(key)
        if cached is not None:
            cached_at, payload = cached
            if time.time() - cached_at <= self._query_cache_ttl_seconds:
                return list(payload)

        rows = self._conn.execute(
            query,
            params,
        ).fetchall()
        payload = [
            ExecutionAnalysisRecord(
                order_id=str(row["order_id"]),
                symbol=str(row["symbol"]),
                predicted_price=float(row["predicted_price"]),
                order_price=float(row["order_price"]),
                execution_price=float(row["execution_price"]),
                slippage_bps=float(row["slippage_bps"]),
                execution_time_ms=float(row["execution_time_ms"]),
                timestamp=datetime.fromisoformat(str(row["timestamp"])),
            )
            for row in rows
        ]
        self._query_cache[key] = (time.time(), payload)
        return payload

    def recent(self, limit: int = 50) -> list[ExecutionAnalysisRecord]:
        return self._cached_query(
            key=f"recent:{limit}",
            query="""
            SELECT order_id, symbol, predicted_price, order_price, execution_price,
                   slippage_bps, execution_time_ms, timestamp
            FROM execution_analysis
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params=(limit,),
        )

    def recent_by_symbol(self, symbol: str, limit: int = 50) -> list[ExecutionAnalysisRecord]:
        return self._cached_query(
            key=f"recent:{symbol}:{limit}",
            query="""
            SELECT order_id, symbol, predicted_price, order_price, execution_price,
                   slippage_bps, execution_time_ms, timestamp
            FROM execution_analysis
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            params=(symbol, limit),
        )
