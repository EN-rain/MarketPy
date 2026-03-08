from __future__ import annotations

import pytest

from backend.features.registry import FeatureDefinition, FeatureRegistry


def test_feature_registry_registers_latest_semver() -> None:
    registry = FeatureRegistry()
    registry.register_feature(
        FeatureDefinition(
            name="alpha",
            version="1.0.0",
            definition={},
            dependencies=[],
            data_sources=["ohlcv"],
            computation_logic="v1",
        )
    )
    registry.register_feature(
        FeatureDefinition(
            name="alpha",
            version="1.1.0",
            definition={},
            dependencies=[],
            data_sources=["ohlcv"],
            computation_logic="v2",
        )
    )

    assert registry.get_feature("alpha").version == "1.1.0"


def test_feature_registry_rejects_non_semver_versions() -> None:
    registry = FeatureRegistry()

    with pytest.raises(ValueError, match="semantic versioning"):
        registry.register_feature(
            FeatureDefinition(
                name="alpha",
                version="1.0",
                definition={},
                dependencies=[],
                data_sources=[],
                computation_logic="invalid",
            )
        )
