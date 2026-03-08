from __future__ import annotations

from pathlib import Path

from backend.ml.model_manager import DeploymentMode, ModelManager


def test_model_manager_registers_deploys_compares_and_rolls_back(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    artifact.write_text("artifact-v1", encoding="utf-8")
    manager = ModelManager(tmp_path / "registry")
    first = manager.register_model(
        model_id="alpha",
        artifact_path=artifact,
        algorithm="xgboost",
        hyperparameters={"depth": 4},
        feature_list=["rsi_14"],
        performance_metrics={"MAE": 0.4, "sharpe_ratio": 1.2},
    )

    artifact.write_text("artifact-v2", encoding="utf-8")
    second = manager.register_model(
        model_id="alpha",
        artifact_path=artifact,
        algorithm="lightgbm",
        hyperparameters={"depth": 5},
        feature_list=["rsi_14", "return_1"],
        performance_metrics={"MAE": 0.3, "sharpe_ratio": 1.4},
    )

    manager.deploy_model("alpha", first.version, mode=DeploymentMode.PRODUCTION, traffic_allocation=1.0)
    manager.deploy_model("alpha", second.version, mode=DeploymentMode.AB_TEST, traffic_allocation=0.4)
    comparison = manager.compare_models("alpha", first.version, second.version)
    rolled = manager.rollback_model("alpha")

    assert first.artifact_checksum
    assert second.version == "1.0.1"
    assert comparison["MAE"] == -0.1
    assert rolled.version == second.version or rolled.version == first.version


def test_model_manager_auto_rollback_and_routing(tmp_path: Path) -> None:
    artifact = tmp_path / "model.bin"
    artifact.write_text("artifact", encoding="utf-8")
    manager = ModelManager(tmp_path / "registry")
    prod = manager.register_model(
        model_id="beta",
        artifact_path=artifact,
        algorithm="xgboost",
        hyperparameters={"lr": 0.1},
        feature_list=["return_1"],
        performance_metrics={"accuracy": 0.6},
    )
    challenger = manager.register_model(
        model_id="beta",
        artifact_path=artifact,
        algorithm="catboost",
        hyperparameters={"lr": 0.2},
        feature_list=["return_1", "rsi_14"],
        performance_metrics={"accuracy": 0.62},
    )
    manager.deploy_model("beta", prod.version, mode=DeploymentMode.PRODUCTION, traffic_allocation=0.6)
    manager.deploy_model("beta", challenger.version, mode=DeploymentMode.AB_TEST, traffic_allocation=0.4)
    manager.record_daily_performance("beta", challenger.version, 0.5)
    manager.record_daily_performance("beta", challenger.version, 0.52)
    manager.record_daily_performance("beta", challenger.version, 0.53)

    triggered = manager.evaluate_automatic_rollback("beta", challenger.version, baseline=0.6)
    routed = manager.route_model_version("beta", sample=0.2)

    assert triggered is True
    assert routed.model_id == "beta"
