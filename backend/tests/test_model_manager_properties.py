from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.ml.model_manager import DeploymentMode, ModelManager


@given(
    allocations=st.lists(
        st.floats(min_value=0.01, max_value=0.99, allow_nan=False, allow_infinity=False),
        min_size=2,
        max_size=5,
    )
)
@settings(max_examples=50, deadline=7000)
@pytest.mark.property_test
def test_property_ab_testing_traffic_allocation(allocations: list[float]) -> None:
    total = sum(allocations)
    normalized = [value / total for value in allocations]
    with TemporaryDirectory() as tmp_dir:
        artifact = Path(tmp_dir) / "model.bin"
        artifact.write_text("artifact", encoding="utf-8")
        manager = ModelManager(Path(tmp_dir) / "registry")
        samples = []
        for index, allocation in enumerate(normalized):
            model = manager.register_model(
                model_id="ab",
                artifact_path=artifact,
                algorithm="xgboost",
                hyperparameters={"index": index},
                feature_list=["return_1"],
                performance_metrics={"accuracy": 0.5 + index / 100},
            )
            mode = DeploymentMode.PRODUCTION if index == 0 else DeploymentMode.AB_TEST
            manager.deploy_model("ab", model.version, mode=mode, traffic_allocation=allocation)
            samples.append(allocation)

        running = 0.0
        for allocation in samples:
            running += allocation
        assert running == pytest.approx(1.0, abs=1e-6)

        picked = manager.route_model_version("ab", sample=0.5)
        assert picked.model_id == "ab"
