"""Feature scaling utilities for ML pipelines."""

from __future__ import annotations

import pickle
from enum import Enum
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pandas as pd
except Exception:  # pragma: no cover - optional in some runtimes
    pd = None  # type: ignore[assignment]

from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler


class ScalerType(str, Enum):
    STANDARD = "standard"
    MINMAX = "minmax"
    ROBUST = "robust"


class UnsafePickleError(ValueError):
    """Raised when a persisted scaler payload contains disallowed pickle globals."""


class _RestrictedUnpickler(pickle.Unpickler):
    _ALLOWED_GLOBALS = {
        ("builtins", "dict"),
        ("builtins", "set"),
        ("builtins", "slice"),
        ("numpy", "dtype"),
        ("numpy", "ndarray"),
        ("numpy._core.multiarray", "_reconstruct"),
        ("numpy._core.multiarray", "scalar"),
        ("numpy.core.multiarray", "_reconstruct"),
        ("numpy.core.multiarray", "scalar"),
        ("numpy.random._pickle", "__randomstate_ctor"),
        ("sklearn.preprocessing._data", "MinMaxScaler"),
        ("sklearn.preprocessing._data", "RobustScaler"),
        ("sklearn.preprocessing._data", "StandardScaler"),
    }

    def find_class(self, module: str, name: str) -> Any:
        if (module, name) not in self._ALLOWED_GLOBALS:
            raise UnsafePickleError(f"Disallowed pickle global: {module}.{name}")
        return super().find_class(module, name)


def _restricted_pickle_load(data: bytes) -> Any:
    return _RestrictedUnpickler(BytesIO(data)).load()


class FeatureScaler:
    """Wrapper around sklearn scalers with persistence helpers."""

    def __init__(self, scaler_type: ScalerType = ScalerType.STANDARD) -> None:
        self.scaler_type = scaler_type
        self._scaler = self._build_scaler(scaler_type)
        self._fitted = False

    @staticmethod
    def _build_scaler(scaler_type: ScalerType) -> Any:
        if scaler_type == ScalerType.MINMAX:
            return MinMaxScaler()
        if scaler_type == ScalerType.ROBUST:
            return RobustScaler()
        return StandardScaler()

    @property
    def fitted(self) -> bool:
        return self._fitted

    def fit(self, data: Any) -> FeatureScaler:
        self._scaler.fit(self._to_array(data))
        self._fitted = True
        return self

    def transform(self, data: Any) -> Any:
        self._assert_fitted()
        transformed = self._scaler.transform(self._to_array(data))
        return self._restore_type(data, transformed)

    def fit_transform(self, data: Any) -> Any:
        transformed = self._scaler.fit_transform(self._to_array(data))
        self._fitted = True
        return self._restore_type(data, transformed)

    def inverse_transform(self, data: Any) -> Any:
        self._assert_fitted()
        restored = self._scaler.inverse_transform(self._to_array(data))
        return self._restore_type(data, restored)

    def fit_train_transform_test(self, train_data: Any, test_data: Any) -> tuple[Any, Any]:
        """Fit on training set only and transform both train/test sets."""
        train_scaled = self.fit_transform(train_data)
        test_scaled = self.transform(test_data)
        return train_scaled, test_scaled

    def save(self, path: str | Path) -> None:
        self._assert_fitted()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "scaler_type": self.scaler_type.value,
            "scaler": self._scaler,
        }
        with out.open("wb") as fh:
            pickle.dump(payload, fh)

    @classmethod
    def load(cls, path: str | Path) -> FeatureScaler:
        in_path = Path(path)
        payload = _restricted_pickle_load(in_path.read_bytes())
        if not isinstance(payload, dict):
            raise UnsafePickleError("Scaler payload must be a dictionary")
        scaler_type = payload.get("scaler_type")
        raw_scaler = payload.get("scaler")
        if scaler_type not in {item.value for item in ScalerType}:
            raise UnsafePickleError(f"Unsupported scaler_type in payload: {scaler_type}")
        if not isinstance(raw_scaler, (StandardScaler, MinMaxScaler, RobustScaler)):
            raise UnsafePickleError(
                f"Unsupported scaler instance in payload: {type(raw_scaler).__name__}"
            )
        scaler = cls(ScalerType(scaler_type))
        scaler._scaler = raw_scaler
        scaler._fitted = True
        return scaler

    @staticmethod
    def _to_array(data: Any) -> np.ndarray:
        if pd is not None and isinstance(data, pd.DataFrame):
            return data.to_numpy()
        if pd is not None and isinstance(data, pd.Series):
            return data.to_numpy().reshape(-1, 1)
        return np.asarray(data)

    @staticmethod
    def _restore_type(template: Any, values: np.ndarray) -> Any:
        if pd is not None and isinstance(template, pd.DataFrame):
            return pd.DataFrame(values, columns=template.columns, index=template.index)
        if pd is not None and isinstance(template, pd.Series):
            return pd.Series(values.reshape(-1), index=template.index, name=template.name)
        return values

    def _assert_fitted(self) -> None:
        if not self._fitted:
            raise RuntimeError("FeatureScaler must be fitted before transform/inverse_transform")
