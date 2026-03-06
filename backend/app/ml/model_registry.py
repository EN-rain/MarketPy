"""Model version management and governance registry."""

from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class ModelStatus(StrEnum):
    TRAINING = "TRAINING"
    STAGING = "STAGING"
    PRODUCTION = "PRODUCTION"
    ARCHIVED = "ARCHIVED"


@dataclass(frozen=True)
class ModelVersion:
    model_id: str
    version: str
    artifact_path: str
    hyperparameters: dict[str, Any]
    training_data_ref: str
    performance_metrics: dict[str, float]
    status: ModelStatus


class ModelRegistry:
    """SQLite-backed model registry with promotion and rollback controls."""

    def __init__(self, db_path: str):
        self.db_path = db_path
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
            CREATE TABLE IF NOT EXISTS model_versions (
                model_id TEXT NOT NULL,
                version TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                hyperparameters TEXT NOT NULL,
                training_data_ref TEXT NOT NULL,
                performance_metrics TEXT NOT NULL,
                status TEXT NOT NULL,
                PRIMARY KEY (model_id, version)
            )
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_model_versions_status
            ON model_versions (model_id, status)
            """
        )
        self._conn.commit()

    def register_model(
        self,
        model_id: str,
        artifact_path: str,
        hyperparameters: dict[str, Any],
        training_data_ref: str,
        performance_metrics: dict[str, float],
        status: ModelStatus = ModelStatus.TRAINING,
    ) -> ModelVersion:
        version = self._next_version(model_id)
        model = ModelVersion(
            model_id=model_id,
            version=version,
            artifact_path=artifact_path,
            hyperparameters=hyperparameters,
            training_data_ref=training_data_ref,
            performance_metrics=performance_metrics,
            status=status,
        )
        self._insert(model)
        return model

    def load_model(self, model_id: str, version: str | None = None) -> ModelVersion:
        if version is None:
            versions = self.list_versions(model_id)
            if not versions:
                raise ValueError("model version not found")
            return versions[0]
        else:
            row = self._conn.execute(
                """
                SELECT * FROM model_versions
                WHERE model_id = ? AND version = ?
                """,
                (model_id, version),
            ).fetchone()
        if row is None:
            raise ValueError("model version not found")
        return self._from_row(row)

    def list_versions(self, model_id: str) -> list[ModelVersion]:
        rows = self._conn.execute(
            """
            SELECT * FROM model_versions
            WHERE model_id = ?
            """,
            (model_id,),
        ).fetchall()
        versions = [self._from_row(row) for row in rows]
        return sorted(versions, key=lambda item: self._version_tuple(item.version), reverse=True)

    def promote_to_production(self, model_id: str, version: str) -> None:
        row = self._conn.execute(
            """
            SELECT version FROM model_versions
            WHERE model_id = ? AND version = ?
            """,
            (model_id, version),
        ).fetchone()
        if row is None:
            raise ValueError("model version not found")

        self._conn.execute(
            """
            UPDATE model_versions
            SET status = ?
            WHERE model_id = ? AND status = ?
            """,
            (ModelStatus.ARCHIVED.value, model_id, ModelStatus.PRODUCTION.value),
        )
        self._conn.execute(
            """
            UPDATE model_versions
            SET status = ?
            WHERE model_id = ? AND version = ?
            """,
            (ModelStatus.PRODUCTION.value, model_id, version),
        )
        self._conn.commit()

    def rollback(self, model_id: str) -> ModelVersion:
        versions = self.list_versions(model_id)
        if len(versions) < 2:
            raise ValueError("not enough versions to rollback")
        current_prod = next(
            (item for item in versions if item.status == ModelStatus.PRODUCTION), None
        )
        if current_prod is None:
            raise ValueError("no production model to rollback")

        ordered = sorted(versions, key=lambda item: self._version_tuple(item.version), reverse=True)
        previous = next((item for item in ordered if item.version != current_prod.version), None)
        if previous is None:
            raise ValueError("previous version not found")
        self.promote_to_production(model_id, previous.version)
        return self.load_model(model_id, previous.version)

    def delete_version(self, model_id: str, version: str) -> None:
        row = self._conn.execute(
            """
            SELECT status FROM model_versions
            WHERE model_id = ? AND version = ?
            """,
            (model_id, version),
        ).fetchone()
        if row is None:
            raise ValueError("model version not found")
        if row["status"] == ModelStatus.PRODUCTION.value:
            raise ValueError("cannot delete production model")
        self._conn.execute(
            """
            DELETE FROM model_versions
            WHERE model_id = ? AND version = ?
            """,
            (model_id, version),
        )
        self._conn.commit()

    def _insert(self, model: ModelVersion) -> None:
        self._conn.execute(
            """
            INSERT INTO model_versions (
                model_id, version, artifact_path, hyperparameters, training_data_ref,
                performance_metrics, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                model.model_id,
                model.version,
                model.artifact_path,
                json.dumps(model.hyperparameters),
                model.training_data_ref,
                json.dumps(model.performance_metrics),
                model.status.value,
            ),
        )
        self._conn.commit()

    def _next_version(self, model_id: str) -> str:
        rows = self._conn.execute(
            """
            SELECT version FROM model_versions
            WHERE model_id = ?
            """,
            (model_id,),
        ).fetchall()
        if not rows:
            return "1.0.0"
        latest = max(self._version_tuple(str(row["version"])) for row in rows)
        major, minor, patch = latest
        return f"{major}.{minor}.{patch + 1}"

    def _from_row(self, row: sqlite3.Row) -> ModelVersion:
        return ModelVersion(
            model_id=str(row["model_id"]),
            version=str(row["version"]),
            artifact_path=str(row["artifact_path"]),
            hyperparameters=json.loads(str(row["hyperparameters"])),
            training_data_ref=str(row["training_data_ref"]),
            performance_metrics=json.loads(str(row["performance_metrics"])),
            status=ModelStatus(str(row["status"])),
        )

    def _version_tuple(self, version: str) -> tuple[int, int, int]:
        if not SEMVER_RE.match(version):
            raise ValueError(f"invalid semantic version: {version}")
        major, minor, patch = version.split(".")
        return int(major), int(minor), int(patch)
