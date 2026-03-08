"""Property tests for model version registry."""

from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.ml.model_registry import ModelRegistry, ModelStatus

SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


# Property 38: Model Version Semantic Versioning
@given(count=st.integers(min_value=1, max_value=20))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_model_version_semantic_versioning(count: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        registry = ModelRegistry(str(Path(tmp_dir) / "models.db"))
        try:
            versions: list[str] = []
            for i in range(count):
                item = registry.register_model(
                    model_id="alpha",
                    artifact_path=f"/models/alpha_{i}.bin",
                    hyperparameters={"lr": 0.01},
                    training_data_ref="dataset:v1",
                    performance_metrics={"acc": 0.8},
                )
                versions.append(item.version)
            assert all(SEMVER_RE.match(v) for v in versions)
        finally:
            registry.close()


# Property 39: Model Artifact Storage Completeness
@given(
    lr=st.floats(min_value=0.0001, max_value=1.0, allow_nan=False, allow_infinity=False),
    depth=st.integers(min_value=1, max_value=50),
    acc=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_model_artifact_storage_completeness(
    lr: float, depth: int, acc: float
) -> None:
    with TemporaryDirectory() as tmp_dir:
        registry = ModelRegistry(str(Path(tmp_dir) / "models.db"))
        try:
            saved = registry.register_model(
                model_id="beta",
                artifact_path="/models/beta.bin",
                hyperparameters={"lr": lr, "depth": depth},
                training_data_ref="dataset:v2",
                performance_metrics={"acc": acc},
                status=ModelStatus.STAGING,
            )
            loaded = registry.load_model("beta", saved.version)
            assert loaded.artifact_path == "/models/beta.bin"
            assert loaded.hyperparameters["depth"] == depth
            assert loaded.training_data_ref == "dataset:v2"
            assert loaded.performance_metrics["acc"] == pytest.approx(acc)
            assert loaded.status == ModelStatus.STAGING
        finally:
            registry.close()


# Property 40: Model Version Loading Correctness
@given(count=st.integers(min_value=2, max_value=15))
@settings(max_examples=100, deadline=7000)
@pytest.mark.property_test
def test_property_model_version_loading_correctness(count: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        registry = ModelRegistry(str(Path(tmp_dir) / "models.db"))
        try:
            versions: list[str] = []
            for i in range(count):
                item = registry.register_model(
                    model_id="gamma",
                    artifact_path=f"/models/gamma_{i}.bin",
                    hyperparameters={"i": i},
                    training_data_ref="dataset:v3",
                    performance_metrics={"acc": 0.5 + (i / 100)},
                )
                versions.append(item.version)

            pick = versions[count // 2]
            loaded_specific = registry.load_model("gamma", pick)
            loaded_latest = registry.load_model("gamma")
            assert loaded_specific.version == pick
            assert loaded_latest.version == versions[-1]
        finally:
            registry.close()


# Property 41: Production Model Deletion Prevention
@given(seed=st.integers(min_value=0, max_value=1000))
@settings(max_examples=50, deadline=7000)
@pytest.mark.property_test
def test_property_production_model_deletion_prevention(seed: int) -> None:
    with TemporaryDirectory() as tmp_dir:
        registry = ModelRegistry(str(Path(tmp_dir) / f"models_{seed}.db"))
        try:
            v1 = registry.register_model(
                model_id="delta",
                artifact_path="/models/delta_1.bin",
                hyperparameters={"lr": 0.1},
                training_data_ref="dataset:v4",
                performance_metrics={"acc": 0.7},
            )
            v2 = registry.register_model(
                model_id="delta",
                artifact_path="/models/delta_2.bin",
                hyperparameters={"lr": 0.2},
                training_data_ref="dataset:v4",
                performance_metrics={"acc": 0.8},
            )
            registry.promote_to_production("delta", v2.version)
            with pytest.raises(ValueError, match="cannot delete production model"):
                registry.delete_version("delta", v2.version)
            registry.delete_version("delta", v1.version)
            remaining = registry.list_versions("delta")
            assert len(remaining) == 1
            assert remaining[0].version == v2.version
        finally:
            registry.close()
