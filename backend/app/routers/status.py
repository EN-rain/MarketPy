"""Status endpoint — system health and mode info."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/status")
async def get_status(request: Request):
    """Return current system status."""
    state = request.app.state.app_state
    return {
        "mode": state.mode.value,
        "is_running": state.is_running,
        "started_at": state.started_at.isoformat(),
        "current_time": datetime.now(UTC).isoformat(),
        "connected_markets": state.connected_markets,
        "connected_markets_count": len(state.connected_markets),
    }
