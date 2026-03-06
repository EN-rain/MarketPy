"""Strategy marketplace backend."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from .models import MarketplaceStrategy, VerifiedMetrics


class StrategyMarketplace:
    """Stores and verifies submitted strategies."""

    def __init__(self, db_path: str):
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
            CREATE TABLE IF NOT EXISTS marketplace_strategies (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                author TEXT NOT NULL,
                description TEXT NOT NULL,
                asset_class TEXT NOT NULL,
                risk_level TEXT NOT NULL,
                methodology TEXT NOT NULL,
                total_return REAL NOT NULL,
                sharpe_ratio REAL NOT NULL,
                max_drawdown REAL NOT NULL,
                out_of_sample_period_days INTEGER NOT NULL
            )
            """
        )
        self._conn.commit()

    def submit_strategy(self, strategy: MarketplaceStrategy) -> None:
        if strategy.metrics.out_of_sample_period_days < 180:
            raise ValueError("out_of_sample period must be >= 180 days")
        self._conn.execute(
            """
            INSERT OR REPLACE INTO marketplace_strategies (
                id, name, author, description, asset_class, risk_level, methodology,
                total_return, sharpe_ratio, max_drawdown, out_of_sample_period_days
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                strategy.id,
                strategy.name,
                strategy.author,
                strategy.description,
                strategy.asset_class,
                strategy.risk_level,
                strategy.methodology,
                strategy.metrics.total_return,
                strategy.metrics.sharpe_ratio,
                strategy.metrics.max_drawdown,
                strategy.metrics.out_of_sample_period_days,
            ),
        )
        self._conn.commit()

    def verify_performance(
        self, returns: Iterable[float], out_of_sample_days: int
    ) -> VerifiedMetrics:
        values = list(returns)
        if out_of_sample_days < 180:
            raise ValueError("out_of_sample period must be >= 180 days")
        if not values:
            return VerifiedMetrics(0.0, 0.0, 0.0, out_of_sample_days)
        total_return = sum(values)
        mean_return = total_return / len(values)
        variance = sum((x - mean_return) ** 2 for x in values) / max(1, len(values) - 1)
        sharpe = 0.0 if variance <= 0 else mean_return / (variance ** 0.5)
        equity = 1.0
        peak = 1.0
        max_dd = 0.0
        for r in values:
            equity *= 1 + r
            peak = max(peak, equity)
            dd = (peak - equity) / peak
            max_dd = max(max_dd, dd)
        return VerifiedMetrics(total_return, sharpe, max_dd, out_of_sample_days)

    def search_strategies(
        self,
        asset_class: str | None = None,
        risk_level: str | None = None,
        min_return: float | None = None,
    ) -> list[MarketplaceStrategy]:
        rows = self._conn.execute("SELECT * FROM marketplace_strategies").fetchall()
        items = [self._from_row(row) for row in rows]
        if asset_class:
            items = [item for item in items if item.asset_class == asset_class]
        if risk_level:
            items = [item for item in items if item.risk_level == risk_level]
        if min_return is not None:
            items = [item for item in items if item.metrics.total_return >= min_return]
        return items

    def _from_row(self, row: sqlite3.Row) -> MarketplaceStrategy:
        metrics = VerifiedMetrics(
            total_return=float(row["total_return"]),
            sharpe_ratio=float(row["sharpe_ratio"]),
            max_drawdown=float(row["max_drawdown"]),
            out_of_sample_period_days=int(row["out_of_sample_period_days"]),
        )
        return MarketplaceStrategy(
            id=str(row["id"]),
            name=str(row["name"]),
            author=str(row["author"]),
            description=str(row["description"]),
            asset_class=str(row["asset_class"]),
            risk_level=str(row["risk_level"]),
            methodology=str(row["methodology"]),
            metrics=metrics,
        )
