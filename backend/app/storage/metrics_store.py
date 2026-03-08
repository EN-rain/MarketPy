"""SQLite-backed storage for integrated metrics datasets."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from backend.app.alerts.models import AlertCondition, TriggeredAlert
from backend.app.execution.slippage_tracker import SlippageRecord
from backend.app.models.market import MarketMetrics, OnChainMetrics, SentimentScore


class MetricsStore:
    """Persist market/on-chain/sentiment metrics for backtesting and analytics."""

    _COUNT_QUERIES = {
        "market_metrics": "SELECT COUNT(*) AS cnt FROM market_metrics",
        "onchain_metrics": "SELECT COUNT(*) AS cnt FROM onchain_metrics",
        "sentiment_scores": "SELECT COUNT(*) AS cnt FROM sentiment_scores",
        "alert_conditions": "SELECT COUNT(*) AS cnt FROM alert_conditions",
        "triggered_alerts": "SELECT COUNT(*) AS cnt FROM triggered_alerts",
        "slippage_records": "SELECT COUNT(*) AS cnt FROM slippage_records",
    }

    def __init__(self, db_path: str):
        self.db_path = db_path
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.init_schema()

    def close(self) -> None:
        self._conn.close()

    def init_schema(self) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS market_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coin_id TEXT NOT NULL,
                volume_24h REAL NOT NULL,
                market_cap REAL NOT NULL,
                circulating_supply REAL NOT NULL,
                total_supply REAL,
                max_supply REAL,
                timestamp TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS onchain_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                mempool_size_mb REAL NOT NULL,
                fee_rate_sat_vb REAL NOT NULL,
                hash_rate_eh_s REAL NOT NULL,
                difficulty REAL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS sentiment_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                score REAL NOT NULL,
                positive_count INTEGER NOT NULL,
                negative_count INTEGER NOT NULL,
                neutral_count INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS alert_conditions (
                id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                condition_type TEXT NOT NULL,
                operator TEXT NOT NULL,
                threshold REAL NOT NULL,
                cooldown_seconds REAL NOT NULL,
                channels TEXT NOT NULL,
                enabled INTEGER NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS triggered_alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                condition_id TEXT NOT NULL,
                market_id TEXT NOT NULL,
                condition_type TEXT NOT NULL,
                operator TEXT NOT NULL,
                threshold REAL NOT NULL,
                observed_value REAL NOT NULL,
                triggered_at TEXT NOT NULL,
                channels TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS slippage_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                expected_price REAL NOT NULL,
                executed_price REAL NOT NULL,
                size REAL NOT NULL,
                slippage_bps REAL NOT NULL,
                volatility REAL NOT NULL,
                volume REAL NOT NULL,
                spread REAL NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_market_metrics_coin_ts
            ON market_metrics (coin_id, timestamp)
            """
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_onchain_metrics_ts ON onchain_metrics (timestamp)"
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sentiment_scores_source_ts
            ON sentiment_scores (source, timestamp)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_triggered_alerts_market_ts
            ON triggered_alerts (market_id, triggered_at)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_slippage_records_symbol_ts
            ON slippage_records (symbol, timestamp)
            """
        )
        self._conn.commit()

    def insert_market_metrics(self, metrics: MarketMetrics) -> None:
        self._conn.execute(
            """
            INSERT INTO market_metrics (
                coin_id, volume_24h, market_cap, circulating_supply,
                total_supply, max_supply, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics.coin_id,
                metrics.volume_24h,
                metrics.market_cap,
                metrics.circulating_supply,
                metrics.total_supply,
                metrics.max_supply,
                metrics.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def insert_onchain_metrics(self, metrics: OnChainMetrics) -> None:
        self._conn.execute(
            """
            INSERT INTO onchain_metrics (
                timestamp, mempool_size_mb, fee_rate_sat_vb, hash_rate_eh_s, difficulty
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                metrics.timestamp.isoformat(),
                metrics.mempool_size_mb,
                metrics.fee_rate_sat_vb,
                metrics.hash_rate_eh_s,
                metrics.difficulty,
            ),
        )
        self._conn.commit()

    def insert_sentiment_score(self, score: SentimentScore) -> None:
        self._conn.execute(
            """
            INSERT INTO sentiment_scores (
                source, score, positive_count, negative_count, neutral_count, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                score.source,
                score.score,
                score.positive_count,
                score.negative_count,
                score.neutral_count,
                score.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def insert_alert_condition(self, condition: AlertCondition) -> None:
        self._conn.execute(
            """
            INSERT OR REPLACE INTO alert_conditions (
                id,
                market_id,
                condition_type,
                operator,
                threshold,
                cooldown_seconds,
                channels,
                enabled
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                condition.id,
                condition.market_id,
                condition.condition_type.value,
                condition.operator.value,
                condition.threshold,
                condition.cooldown_seconds,
                ",".join(condition.channels),
                1 if condition.enabled else 0,
            ),
        )
        self._conn.commit()

    def insert_triggered_alert(self, alert: TriggeredAlert) -> None:
        self._conn.execute(
            """
            INSERT INTO triggered_alerts (
                condition_id,
                market_id,
                condition_type,
                operator,
                threshold,
                observed_value,
                triggered_at,
                channels
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.condition_id,
                alert.market_id,
                alert.condition_type.value,
                alert.operator.value,
                alert.threshold,
                alert.observed_value,
                alert.triggered_at.isoformat(),
                ",".join(alert.channels),
            ),
        )
        self._conn.commit()

    def insert_slippage_record(self, record: SlippageRecord) -> None:
        self._conn.execute(
            """
            INSERT INTO slippage_records (
                symbol, side, expected_price, executed_price, size, slippage_bps,
                volatility, volume, spread, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.symbol,
                record.side,
                record.expected_price,
                record.executed_price,
                record.size,
                record.slippage_bps,
                record.volatility,
                record.volume,
                record.spread,
                record.timestamp.isoformat(),
            ),
        )
        self._conn.commit()

    def count_rows(self, table_name: str) -> int:
        query = self._COUNT_QUERIES.get(table_name)
        if query is None:
            raise ValueError(f"Unsupported table for count_rows: {table_name}")
        row = self._conn.execute(query).fetchone()
        return int(row["cnt"]) if row else 0
