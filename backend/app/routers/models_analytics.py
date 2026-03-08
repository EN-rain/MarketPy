"""AI model analytics endpoints."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.app.models.config import settings
from backend.ml.inference import DERIVED_MODEL_FALLBACKS
from backend.ml.feature_importance_tracker import FeatureImportanceTracker
from backend.ml.prediction_tracker import get_prediction_tracker

router = APIRouter()


def _format_last_trained(timestamp: float) -> str:
    modified = datetime.fromtimestamp(timestamp, tz=UTC)
    delta = max((datetime.now(UTC) - modified).total_seconds(), 0.0)
    if delta < 60:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{int(delta // 3600)} h ago"
    return f"{int(delta // 86400)} d ago"


def _load_json_if_exists(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@router.get("/models/registry")
async def get_model_registry():
    """List discovered model artifacts for the terminal models page."""
    model_dir = Path(settings.model_dir)
    artifacts = sorted(model_dir.glob("*.joblib")) if model_dir.exists() else []
    items: list[dict] = []
    item_by_id: dict[str, dict] = {}

    for artifact in artifacts:
        model_id = artifact.stem
        metrics = _load_json_if_exists(artifact.with_name(f"{model_id}_metrics.json"))
        horizon = model_id.split("_")[-1] if "_" in model_id else "n/a"
        accuracy = float(
            metrics.get("accuracy")
            or metrics.get("directional_accuracy")
            or metrics.get("score")
            or 0.0
        )
        if accuracy <= 1.0:
            accuracy *= 100.0
        model_type = str(
            metrics.get("model_type")
            or metrics.get("type")
            or metrics.get("estimator")
            or "artifact"
        )
        dataset = str(metrics.get("dataset") or metrics.get("dataset_name") or "parquet")
        params_value = metrics.get("params_count") or metrics.get("parameters") or metrics.get("features")
        params = str(params_value) if params_value is not None else "--"
        status = "active" if artifact.exists() else "inactive"

        item = {
            "id": model_id,
            "name": model_id.replace("_", " ").title(),
            "type": model_type,
            "accuracy": round(accuracy, 2),
            "horizon": horizon,
            "last_trained": _format_last_trained(artifact.stat().st_mtime),
            "status": status,
            "params": params,
            "dataset": dataset,
            "artifact_path": str(artifact),
        }
        items.append(item)
        item_by_id[model_id] = item

    for derived_model, fallback_model in DERIVED_MODEL_FALLBACKS.items():
        if derived_model in item_by_id or fallback_model not in item_by_id:
            continue
        source_item = item_by_id[fallback_model]
        item = {
            **source_item,
            "id": derived_model,
            "name": derived_model.replace("_", " ").title(),
            "horizon": derived_model.split("_")[-1],
            "type": f"{source_item['type']} (derived)",
            "dataset": f"{source_item['dataset']} / derived",
            "derived_from": fallback_model,
        }
        items.append(item)

    return {"items": items}


@router.get("/models/analytics")
async def get_models_analytics(
    market_id: str | None = Query(default=None),
    horizon: str | None = Query(default="5m"),
    limit: int = Query(default=100, ge=10, le=500),
):
    tracker = get_prediction_tracker()
    summary = tracker.get_summary()
    recent = tracker.get_recent(limit=limit)
    chart = tracker.get_chart_points(market_id=market_id, horizon=horizon, limit=limit)
    live_preview = tracker.get_live_preview(limit=limit)
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
