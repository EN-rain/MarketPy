"""Audit log storage for decisions, deployments, and risk events."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class AuditEntry:
    event_type: str
    reason: str
    payload: dict[str, Any]
    created_at: datetime


class AuditLogger:
    def __init__(self, db_path: str, retention_days: int = 365) -> None:
        self.retention_days = retention_days
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                reason TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_event_ts ON audit_logs (event_type, created_at)"
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def _insert(self, event_type: str, reason: str, payload: dict[str, Any], timestamp: datetime | None = None) -> None:
        ts = timestamp or datetime.now(UTC)
        self._conn.execute(
            "INSERT INTO audit_logs (event_type, reason, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (event_type, reason, json.dumps(payload, sort_keys=True), ts.isoformat()),
        )
        self._conn.commit()

    def log_trading_decision(self, payload: dict[str, Any], reason: str) -> None:
        self._insert("trading_decision", reason, payload)

    def log_model_deployment(self, payload: dict[str, Any], reason: str) -> None:
        self._insert("model_deployment", reason, payload)

    def log_model_rollback(self, payload: dict[str, Any], reason: str) -> None:
        self._insert("model_rollback", reason, payload)

    def log_config_change(self, payload: dict[str, Any], reason: str) -> None:
        self._insert("config_change", reason, payload)

    def log_risk_breach(self, payload: dict[str, Any], reason: str) -> None:
        self._insert("risk_breach", reason, payload)

    def cleanup_retention(self, now: datetime | None = None) -> int:
        reference = now or datetime.now(UTC)
        cutoff = reference - timedelta(days=self.retention_days)
        cursor = self._conn.execute("DELETE FROM audit_logs WHERE created_at < ?", (cutoff.isoformat(),))
        self._conn.commit()
        return int(cursor.rowcount or 0)

    def count_rows(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS cnt FROM audit_logs").fetchone()
        return int(row["cnt"]) if row else 0
