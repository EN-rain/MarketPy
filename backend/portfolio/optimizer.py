"""Portfolio optimization engines."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class PortfolioWeights:
    method: str
    weights: dict[str, float]


class PortfolioOptimizer:
    """Supports Markowitz, risk parity, and Black-Litterman style blends."""

    def _normalize_long_only(self, values: np.ndarray, assets: list[str]) -> dict[str, float]:
        clipped = np.clip(values, 0.0, None)
        total = float(clipped.sum())
        if total <= 0:
            equal = 1.0 / max(len(assets), 1)
            return {asset: equal for asset in assets}
        return {asset: float(weight / total) for asset, weight in zip(assets, clipped, strict=False)}

    def mean_variance(self, returns: pd.DataFrame) -> PortfolioWeights:
        assets = list(returns.columns)
        mu = returns.mean().to_numpy(dtype=float)
        cov = returns.cov().to_numpy(dtype=float)
        inv_cov = np.linalg.pinv(cov)
        raw = inv_cov @ mu
        return PortfolioWeights(method="mean_variance", weights=self._normalize_long_only(raw, assets))

    def risk_parity(self, returns: pd.DataFrame) -> PortfolioWeights:
        assets = list(returns.columns)
        vol = returns.std(ddof=0).replace(0.0, np.nan).fillna(1.0).to_numpy(dtype=float)
        inverse_vol = 1.0 / vol
        return PortfolioWeights(method="risk_parity", weights=self._normalize_long_only(inverse_vol, assets))

    def black_litterman(self, returns: pd.DataFrame, views: dict[str, float], tau: float = 0.05) -> PortfolioWeights:
        assets = list(returns.columns)
        prior = returns.mean().to_numpy(dtype=float)
        view_vector = np.array([views.get(asset, 0.0) for asset in assets], dtype=float)
        blended = ((1.0 - tau) * prior) + (tau * view_vector)
        cov = returns.cov().to_numpy(dtype=float)
        inv_cov = np.linalg.pinv(cov)
        raw = inv_cov @ blended
        return PortfolioWeights(method="black_litterman", weights=self._normalize_long_only(raw, assets))

    def optimal_weights(self, returns: pd.DataFrame, *, method: str, views: dict[str, float] | None = None) -> PortfolioWeights:
        if method == "mean_variance":
            return self.mean_variance(returns)
        if method == "risk_parity":
            return self.risk_parity(returns)
        if method == "black_litterman":
            return self.black_litterman(returns, views or {})
        raise ValueError(f"Unsupported optimization method: {method}")

    def apply_correlation_constraints(
        self,
        weights: dict[str, float],
        returns: pd.DataFrame,
        *,
        correlation_threshold: float = 0.7,
        max_cluster_weight: float = 0.4,
    ) -> dict[str, float]:
        """Limit exposure of highly correlated asset clusters."""
        if not weights:
            return {}
        corr = returns.corr(numeric_only=True).fillna(0.0).abs()
        assets = list(weights.keys())
        adjusted = dict(weights)
        visited: set[str] = set()

        for asset in assets:
            if asset in visited or asset not in corr.columns:
                continue
            cluster = {peer for peer in assets if corr.loc[asset, peer] >= correlation_threshold}
            cluster.add(asset)
            visited.update(cluster)
            cluster_weight = sum(adjusted.get(name, 0.0) for name in cluster)
            if cluster_weight <= max_cluster_weight or cluster_weight <= 0:
                continue
            scale = max_cluster_weight / cluster_weight
            for name in cluster:
                adjusted[name] = adjusted.get(name, 0.0) * scale

        total = sum(max(value, 0.0) for value in adjusted.values())
        if total <= 0:
            equal = 1.0 / len(adjusted)
            return {name: equal for name in adjusted}
        return {name: float(max(value, 0.0) / total) for name, value in adjusted.items()}
