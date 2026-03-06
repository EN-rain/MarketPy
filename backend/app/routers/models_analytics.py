"""AI model analytics endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.config import settings
from backend.ml.feature_importance_tracker import FeatureImportanceTracker
from backend.ml.prediction_tracker import get_prediction_tracker

router = APIRouter()


@router.get("/models/analytics")
async def get_models_analytics(
    market_id: str | None = Query(default=None),
    horizon: str | None = Query(default="1h"),
    limit: int = Query(default=100, ge=10, le=500),
):
    tracker = get_prediction_tracker()
    summary = tracker.get_summary()
    recent = tracker.get_recent(limit=50)
    chart = tracker.get_chart_points(market_id=market_id, horizon=horizon, limit=limit)
    live_preview = tracker.get_live_preview(limit=50)
    return {
        "summary": summary,
        "recent_predictions": recent,
        "live_preview": live_preview,
        "chart": chart,
        "filters": {"market_id": market_id, "horizon": horizon, "limit": limit},
    }


@router.get("/models/{model_id}/feature_importance")
async def get_model_feature_importance(model_id: str):
    tracker = FeatureImportanceTracker(output_dir=f"{settings.model_dir}/feature_importance")
    payload = tracker.load(model_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"No feature importance found for model '{model_id}'")
    return payload
