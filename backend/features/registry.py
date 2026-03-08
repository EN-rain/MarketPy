"""Feature registry with versioned metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable


SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


@dataclass(slots=True)
class FeatureDefinition:
    name: str
    version: str
    definition: dict[str, Any]
    dependencies: list[str]
    data_sources: list[str]
    computation_logic: str
    compute_fn: Callable[[Any], float] | None = None


class FeatureRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], FeatureDefinition] = {}

    def register_feature(self, feature: FeatureDefinition) -> None:
        if not SEMVER_RE.match(feature.version):
            raise ValueError("Feature version must use semantic versioning: major.minor.patch")
        self._definitions[(feature.name, feature.version)] = feature

    def get_feature(self, name: str, version: str | None = None) -> FeatureDefinition:
        if version is not None:
            return self._definitions[(name, version)]
        candidates = [item for key, item in self._definitions.items() if key[0] == name]
        if not candidates:
            raise KeyError(name)
        return sorted(candidates, key=lambda item: tuple(int(part) for part in item.version.split(".")))[-1]

    def metadata(self, name: str, version: str | None = None) -> dict[str, Any]:
        feature = self.get_feature(name, version)
        return {
            "name": feature.name,
            "version": feature.version,
            "definition": feature.definition,
            "dependencies": feature.dependencies,
            "data_sources": feature.data_sources,
            "computation_logic": feature.computation_logic,
        }
