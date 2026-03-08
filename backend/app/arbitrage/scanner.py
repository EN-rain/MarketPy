"""Cross-exchange arbitrage scanner."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    gross_profit_pct: float
    net_profit_pct: float
    detected_at: datetime


class ArbitrageScanner:
    """Scans exchange quotes and tracks opportunity metrics."""

    def __init__(self, db_path: str, min_profit_threshold_pct: float = 0.5):
        self.min_profit_threshold_pct = min_profit_threshold_pct
        self._history: list[ArbitrageOpportunity] = []
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self._conn.close()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS arbitrage_opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                buy_exchange TEXT NOT NULL,
                sell_exchange TEXT NOT NULL,
                buy_price REAL NOT NULL,
                sell_price REAL NOT NULL,
                gross_profit_pct REAL NOT NULL,
                net_profit_pct REAL NOT NULL,
                detected_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_arb_symbol_detected_at
            ON arbitrage_opportunities (symbol, detected_at)
            """
        )
        self._conn.commit()

    def scan_opportunities(
        self, symbol: str, exchange_prices: dict[str, float]
    ) -> list[ArbitrageOpportunity]:
        if len(exchange_prices) < 2:
            return []
        opportunities: list[ArbitrageOpportunity] = []
        exchanges = list(exchange_prices.keys())
        for buy in exchanges:
            for sell in exchanges:
                if buy == sell:
                    continue
                buy_price = exchange_prices[buy]
                sell_price = exchange_prices[sell]
                if buy_price <= 0 or sell_price <= 0:
                    continue
                gross = ((sell_price - buy_price) / buy_price) * 100.0
                net = self.calculate_net_profit(
                    gross_profit_pct=gross, fee_pct=0.1, slippage_pct=0.1
                )
                if net < self.min_profit_threshold_pct:
                    continue
                opp = ArbitrageOpportunity(
                    symbol=symbol,
                    buy_exchange=buy,
                    sell_exchange=sell,
                    buy_price=buy_price,
                    sell_price=sell_price,
                    gross_profit_pct=gross,
                    net_profit_pct=net,
                    detected_at=datetime.now(UTC),
                )
                opportunities.append(opp)
                self._persist(opp)
                self._history.append(opp)
        return opportunities

    def calculate_net_profit(
        self, gross_profit_pct: float, fee_pct: float, slippage_pct: float
    ) -> float:
        return gross_profit_pct - fee_pct - slippage_pct

    def generate_alerts(self, opportunities: list[ArbitrageOpportunity]) -> list[str]:
        alerts: list[str] = []
        for item in opportunities:
            if item.net_profit_pct >= self.min_profit_threshold_pct:
                alerts.append(
                    f"Arb {item.symbol}: buy {item.buy_exchange} @ {item.buy_price:.4f}, "
                    f"sell {item.sell_exchange} @ {item.sell_price:.4f}, "
                    f"net={item.net_profit_pct:.3f}%"
                )
        return alerts

    def track_opportunity_metrics(self, symbol: str) -> dict[str, float]:
        symbol_items = [item for item in self._history if item.symbol == symbol]
        if not symbol_items:
            return {
                "count": 0.0,
                "avg_detection_interval_seconds": 0.0,
                # Backward compatibility for existing consumers.
                "avg_duration_seconds": 0.0,
            }
        ordered = sorted(symbol_items, key=lambda item: item.detected_at)
        durations: list[float] = []
        for a, b in zip(ordered, ordered[1:], strict=False):
            durations.append((b.detected_at - a.detected_at).total_seconds())
        avg_interval = sum(durations) / len(durations) if durations else 0.0
        return {
            "count": float(len(symbol_items)),
            "avg_detection_interval_seconds": avg_interval,
            # Deprecated alias for compatibility.
            "avg_duration_seconds": avg_interval,
        }

    def count_rows(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM arbitrage_opportunities").fetchone()
        return int(row["cnt"]) if row else 0

    def _persist(self, item: ArbitrageOpportunity) -> None:
        self._conn.execute(
            """
            INSERT INTO arbitrage_opportunities (
                symbol, buy_exchange, sell_exchange, buy_price, sell_price,
                gross_profit_pct, net_profit_pct, detected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.symbol,
                item.buy_exchange,
                item.sell_exchange,
                item.buy_price,
                item.sell_price,
                item.gross_profit_pct,
                item.net_profit_pct,
                item.detected_at.isoformat(),
            ),
        )
        self._conn.commit()
