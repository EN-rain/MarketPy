"""Monitoring dashboard endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/monitoring/dashboard")
async def get_monitoring_dashboard(request: Request):
    dashboard = request.app.state.monitoring_dashboard
    return dashboard.payload()


@router.get("/monitoring/system-health")
async def get_system_health(request: Request):
    dashboard = request.app.state.monitoring_dashboard
    return dashboard.system_health()


@router.get("/monitoring/alerts")
async def get_active_alerts(request: Request):
    dashboard = request.app.state.monitoring_dashboard
    return {"items": dashboard.active_alerts()}
