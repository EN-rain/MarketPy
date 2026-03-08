"""Tests for feature scaling wrappers."""

from __future__ import annotations

import pickle

import numpy as np
import pytest

from backend.dataset.scalers import FeatureScaler, ScalerType, UnsafePickleError


def test_scaler_round_trip_standard() -> None:
    arr = np.array([[1.0, 10.0], [2.0, 20.0], [3.0, 30.0]])
    scaler = FeatureScaler(ScalerType.STANDARD)
    scaled = scaler.fit_transform(arr)
    restored = scaler.inverse_transform(scaled)
    assert np.allclose(arr, restored, atol=1e-6)


def test_fit_train_transform_test() -> None:
    train = np.array([[1.0], [2.0], [3.0]])
    test = np.array([[4.0], [5.0]])
    scaler = FeatureScaler(ScalerType.MINMAX)
    train_scaled, test_scaled = scaler.fit_train_transform_test(train, test)
    assert train_scaled.min() >= 0.0
    assert train_scaled.max() <= 1.0
    assert test_scaled.shape == test.shape


def test_scaler_save_load_round_trip(tmp_path) -> None:
    path = tmp_path / "scaler.pkl"
    values = np.array([[1.0], [2.0], [3.0]])
    scaler = FeatureScaler(ScalerType.STANDARD)
    scaler.fit(values)
    scaler.save(path)

    loaded = FeatureScaler.load(path)
    restored = loaded.inverse_transform(loaded.transform(values))
    assert np.allclose(values, restored, atol=1e-6)


def test_scaler_load_rejects_unsafe_pickle(tmp_path) -> None:
    class Dangerous:
        def __reduce__(self):
            return (eval, ("1 + 1",))

    path = tmp_path / "unsafe.pkl"
    with path.open("wb") as fh:
        pickle.dump({"scaler_type": ScalerType.STANDARD.value, "scaler": Dangerous()}, fh)

    with pytest.raises(UnsafePickleError):
        FeatureScaler.load(path)
