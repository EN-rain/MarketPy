"""Validation helpers for computed features."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite


@dataclass(slots=True)
class FeatureValidationResult:
    valid: bool
    errors: list[str]


class FeatureValidator:
    def validate(self, features: dict[str, float], *, computed_at: datetime, now: datetime) -> FeatureValidationResult:
        errors: list[str] = []
        for name, value in features.items():
            if not isfinite(value):
                errors.append(f"{name} must be finite")
            if abs(value) > 1e9:
                errors.append(f"{name} exceeds allowed range")
        if computed_at < now - timedelta(seconds=60):
            errors.append("feature set is stale")
        return FeatureValidationResult(valid=not errors, errors=errors)
