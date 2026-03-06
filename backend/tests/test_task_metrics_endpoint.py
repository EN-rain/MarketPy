"""Tests for task metrics monitoring endpoint."""


import pytest
from fastapi.testclient import TestClient

from backend.app.main import AppConfig, create_app
from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig


def test_task_metrics_endpoint_returns_metrics():
    """Test that /api/metrics/tasks endpoint returns task manager metrics."""
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        response = client.get("/api/metrics/tasks")

        assert response.status_code == 200
        data = response.json()

        # Verify all required fields are present
        assert "current_task_count" in data
        assert "queue_depth" in data
        assert "rejected_count" in data

        # Verify metrics are non-negative integers
        assert isinstance(data["current_task_count"], int)
        assert isinstance(data["queue_depth"], int)
        assert isinstance(data["rejected_count"], int)
        assert data["current_task_count"] >= 0
        assert data["queue_depth"] >= 0
        assert data["rejected_count"] >= 0


def test_task_metrics_endpoint_includes_additional_metrics():
    """Test that endpoint includes completed_count and failed_count."""
    test_config = AppConfig(enable_binance_stream=False)
    app = create_app(test_config)
    with TestClient(app) as client:
        response = client.get("/api/metrics/tasks")

        assert response.status_code == 200
        data = response.json()

        # Verify additional metrics are present
        assert "completed_count" in data
        assert "failed_count" in data

        # Verify they are non-negative integers
        assert isinstance(data["completed_count"], int)
        assert isinstance(data["failed_count"], int)
        assert data["completed_count"] >= 0
        assert data["failed_count"] >= 0


@pytest.mark.asyncio
async def test_task_metrics_reflect_task_manager_state():
    """Test that metrics endpoint reflects actual task manager state."""
    # Create a task manager with known state
    config = TaskManagerConfig(
        max_concurrent_tasks=5,
        queue_max_size=10,
        priority_levels=3
    )
    task_manager = BoundedTaskManager(config)

    try:
        # Get initial metrics
        metrics = task_manager.get_metrics()

        # Verify initial state
        assert metrics.current_task_count == 0
        assert metrics.queue_depth == 0
        assert metrics.rejected_count == 0
        assert metrics.completed_count == 0
        assert metrics.failed_count == 0
    finally:
        await task_manager.shutdown(timeout=1.0)
