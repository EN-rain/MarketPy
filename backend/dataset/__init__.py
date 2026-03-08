"""Dataset package with feature engineering, indicators, and scaling."""

from backend.dataset.features import (
    add_labels,
    add_lag_returns,
    add_rolling_volatility,
    add_spread_features,
    add_time_features,
    build_feature_matrix,
    compute_macd,
    compute_rsi,
    get_feature_columns,
)
from backend.dataset.indicators import (
    DEFAULT_INDICATORS,
    IndicatorConfig,
    IndicatorLibrary,
    IndicatorPipeline,
)
from backend.dataset.scalers import FeatureScaler, ScalerType

__all__ = [
    "DEFAULT_INDICATORS",
    "FeatureScaler",
    "IndicatorConfig",
    "IndicatorLibrary",
    "IndicatorPipeline",
    "ScalerType",
    "add_labels",
    "add_lag_returns",
    "add_rolling_volatility",
    "add_spread_features",
    "add_time_features",
    "build_feature_matrix",
    "compute_macd",
    "compute_rsi",
    "get_feature_columns",
]
