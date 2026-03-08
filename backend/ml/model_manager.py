"""Model management infrastructure with deployment and rollback controls."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from statistics import mean
from typing import Any


class DeploymentMode(StrEnum):
    PRODUCTION = "production"
    SHADOW = "shadow"
    AB_TEST = "ab_test"


@dataclass(slots=True)
class ManagedModel:
    model_id: str
    version: str
    algorithm: str
    hyperparameters: dict[str, Any]
    feature_list: list[str]
    performance_metrics: dict[str, float]
    artifact_path: str
    artifact_checksum: str
    deployment_mode: str = "registered"
    traffic_allocation: float = 0.0
    rollback_history: list[str] = field(default_factory=list)
    performance_history: list[float] = field(default_factory=list)


class ModelManager:
    def __init__(self, storage_dir: str | Path) -> None:
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.storage_dir / "registry.json"
        self._models = self._load_registry()

    def _load_registry(self) -> dict[str, list[ManagedModel]]:
        if not self.registry_path.exists():
            return {}
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        return {
            model_id: [ManagedModel(**item) for item in items]
            for model_id, items in payload.items()
        }

    def _save_registry(self) -> None:
        payload = {model_id: [asdict(model) for model in items] for model_id, items in self._models.items()}
        self.registry_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        digest.update(path.read_bytes())
        return digest.hexdigest()

    def _next_version(self, model_id: str) -> str:
        versions = self._models.get(model_id, [])
        if not versions:
            return "1.0.0"
        latest = sorted((tuple(int(part) for part in item.version.split(".")) for item in versions))[-1]
        return f"{latest[0]}.{latest[1]}.{latest[2] + 1}"

    def register_model(
        self,
        *,
        model_id: str,
        artifact_path: str | Path,
        algorithm: str,
        hyperparameters: dict[str, Any],
        feature_list: list[str],
        performance_metrics: dict[str, float],
    ) -> ManagedModel:
        source = Path(artifact_path)
        version = self._next_version(model_id)
        target_dir = self.storage_dir / model_id / version
        target_dir.mkdir(parents=True, exist_ok=True)
        target_artifact = target_dir / source.name
        shutil.copy2(source, target_artifact)
        model = ManagedModel(
            model_id=model_id,
            version=version,
            algorithm=algorithm,
            hyperparameters=hyperparameters,
            feature_list=feature_list,
            performance_metrics=performance_metrics,
            artifact_path=str(target_artifact),
            artifact_checksum=self._checksum(target_artifact),
        )
        self._models.setdefault(model_id, []).append(model)
        self._save_registry()
        return model

    def get_model(self, model_id: str, version: str | None = None, deployment_mode: DeploymentMode | None = None) -> ManagedModel:
        candidates = self._models.get(model_id, [])
        if deployment_mode is not None:
            candidates = [model for model in candidates if model.deployment_mode == deployment_mode.value]
        if version is not None:
            candidates = [model for model in candidates if model.version == version]
        if not candidates:
            raise ValueError("model not found")
        return sorted(candidates, key=lambda item: tuple(int(part) for part in item.version.split(".")), reverse=True)[0]

    def deploy_model(self, model_id: str, version: str, *, mode: DeploymentMode, traffic_allocation: float = 1.0) -> ManagedModel:
        model = self.get_model(model_id, version)
        if mode == DeploymentMode.PRODUCTION:
            for item in self._models.get(model_id, []):
                if item.deployment_mode == DeploymentMode.PRODUCTION.value:
                    item.deployment_mode = "registered"
                    item.traffic_allocation = 0.0
        model.deployment_mode = mode.value
        model.traffic_allocation = traffic_allocation
        self._save_registry()
        return model

    def rollback_model(self, model_id: str) -> ManagedModel:
        versions = sorted(self._models.get(model_id, []), key=lambda item: tuple(int(part) for part in item.version.split(".")), reverse=True)
        current = next((item for item in versions if item.deployment_mode == DeploymentMode.PRODUCTION.value), None)
        if current is None or len(versions) < 2:
            raise ValueError("no previous model available for rollback")
        previous = next(item for item in versions if item.version != current.version)
        current.rollback_history.append(previous.version)
        current.deployment_mode = "registered"
        current.traffic_allocation = 0.0
        previous.deployment_mode = DeploymentMode.PRODUCTION.value
        previous.traffic_allocation = 1.0
        self._save_registry()
        return previous

    def compare_models(self, model_id: str, version_a: str, version_b: str) -> dict[str, float]:
        first = self.get_model(model_id, version_a)
        second = self.get_model(model_id, version_b)
        metrics = {"MAE", "RMSE", "directional_accuracy", "Sharpe ratio", "Sharpe_ratio", "sharpe_ratio"}
        result: dict[str, float] = {}
        for key in set(first.performance_metrics) | set(second.performance_metrics):
            if key in metrics or True:
                result[key] = round(
                    float(second.performance_metrics.get(key, 0.0) - first.performance_metrics.get(key, 0.0)),
                    10,
                )
        return result

    def record_daily_performance(self, model_id: str, version: str, metric: float) -> ManagedModel:
        model = self.get_model(model_id, version)
        model.performance_history.append(metric)
        self._save_registry()
        return model

    def evaluate_automatic_rollback(self, model_id: str, version: str, baseline: float) -> bool:
        model = self.get_model(model_id, version)
        if len(model.performance_history) < 3:
            return False
        recent = model.performance_history[-3:]
        if all(value <= baseline * 0.9 for value in recent):
            self.rollback_model(model_id)
            return True
        return False

    def route_model_version(self, model_id: str, sample: float) -> ManagedModel:
        active = [model for model in self._models.get(model_id, []) if model.deployment_mode in {DeploymentMode.PRODUCTION.value, DeploymentMode.AB_TEST.value}]
        if not active:
            raise ValueError("no deployed model available")
        running = 0.0
        for model in sorted(active, key=lambda item: item.version):
            running += model.traffic_allocation
            if sample <= running:
                return model
        return active[-1]
