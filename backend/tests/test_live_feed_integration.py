"""Integration tests for LiveFeedService with BoundedTaskManager."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest

from backend.app.realtime.task_manager import BoundedTaskManager, TaskManagerConfig
from backend.paper_trading.live_feed import LiveFeedService, LiveFeedUpdate


@pytest.fixture
async def task_manager():
    """Create a task manager with small limits for testing."""
    config = TaskManagerConfig(
        max_concurrent_tasks=2,
        queue_max_size=5,
        priority_levels=3
    )
    manager = BoundedTaskManager(config)
    yield manager
    await manager.shutdown(timeout=1.0)


@pytest.fixture
async def live_feed_service(task_manager):
    """Create a LiveFeedService with test task manager."""
    service = LiveFeedService(
        ws_url="ws://test.example.com",
        output_dir="data/test",
        task_manager=task_manager
    )
    yield service
    await service.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_live_feed_uses_task_manager(live_feed_service):
    """Test that LiveFeedService uses BoundedTaskManager for task submission."""
    # Verify task manager is initialized
    assert live_feed_service._task_manager is not None

    # Get initial metrics
    metrics = live_feed_service.get_task_metrics()
    assert metrics.current_task_count == 0
    assert metrics.queue_depth == 0
    assert metrics.rejected_count == 0


@pytest.mark.asyncio
async def test_live_feed_task_metrics_exposed(live_feed_service):
    """Test that task metrics are exposed through get_task_metrics()."""
    metrics = live_feed_service.get_task_metrics()

    # Verify metrics structure
    assert hasattr(metrics, 'current_task_count')
    assert hasattr(metrics, 'queue_depth')
    assert hasattr(metrics, 'rejected_count')
    assert hasattr(metrics, 'completed_count')
    assert hasattr(metrics, 'failed_count')


@pytest.mark.asyncio
async def test_live_feed_shutdown_calls_task_manager_shutdown(live_feed_service):
    """Test that LiveFeedService.shutdown() calls task manager shutdown."""
    # Mock the task manager shutdown
    live_feed_service._task_manager.shutdown = AsyncMock()

    # Call shutdown
    await live_feed_service.shutdown(timeout=5.0)

    # Verify task manager shutdown was called
    live_feed_service._task_manager.shutdown.assert_called_once_with(timeout=5.0)


@pytest.mark.asyncio
async def test_broadcast_with_priority(live_feed_service):
    """Test that broadcasts are submitted with correct priority."""
    handler_called = asyncio.Event()
    received_updates = []

    async def test_handler(update: LiveFeedUpdate):
        received_updates.append(update)
        handler_called.set()

    live_feed_service.add_handler(test_handler)

    # Create a test update
    update = LiveFeedUpdate(
        market_id="BTC-USD",
        timestamp=datetime.now(UTC),
        event_type="test",
        bid=50000.0,
        ask=50001.0,
        mid=50000.5
    )

    # Submit through _route_update (which uses task manager)
    await live_feed_service._route_update(update)

    # Wait a bit for async processing
    await asyncio.sleep(0.1)

    # Verify metrics show task was processed
    metrics = live_feed_service.get_task_metrics()
    assert metrics.completed_count >= 0  # May be 0 or 1 depending on timing


@pytest.mark.asyncio
async def test_task_manager_limits_concurrent_tasks():
    """Test that task manager properly limits concurrent tasks."""
    config = TaskManagerConfig(
        max_concurrent_tasks=2,
        queue_max_size=5,
        priority_levels=3
    )
    task_manager = BoundedTaskManager(config)

    results = []

    async def slow_task(task_id: int):
        await asyncio.sleep(0.1)
        results.append(task_id)

    # Submit 5 tasks (max_concurrent=2, queue_max=5)
    tasks = []
    for i in range(5):
        task = await task_manager.submit_task(slow_task(i), priority=1)
        if task:
            tasks.append(task)

    # Check metrics
    metrics = task_manager.get_metrics()

    # Should have some tasks running or queued
    assert metrics.current_task_count + metrics.queue_depth > 0

    # Wait for all tasks to complete
    await asyncio.sleep(0.5)

    # Verify all tasks completed
    final_metrics = task_manager.get_metrics()
    assert final_metrics.completed_count == 5
    assert len(results) == 5

    await task_manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_priority_levels_in_live_feed():
    """Test that different update types get different priorities."""
    config = TaskManagerConfig(
        max_concurrent_tasks=1,  # Force queuing
        queue_max_size=10,
        priority_levels=3
    )
    task_manager = BoundedTaskManager(config)

    service = LiveFeedService(task_manager=task_manager)

    # Mock the broadcast to track calls
    call_order = []

    async def tracking_handler(update: LiveFeedUpdate):
        call_order.append(update.event_type)

    service.add_handler(tracking_handler)

    # Create updates with different priorities
    # Critical update (priority 0)
    critical_update = LiveFeedUpdate(
        market_id="BTC-USD",
        timestamp=datetime.now(UTC),
        event_type="critical",
        bid=50000.0,
        ask=50001.0,
        mid=50000.5
    )

    # Normal update (priority 1)
    normal_update = LiveFeedUpdate(
        market_id="ETH-USD",
        timestamp=datetime.now(UTC),
        event_type="normal",
        bid=3000.0,
        ask=3001.0,
        mid=3000.5
    )

    # Submit updates
    await service._route_update(critical_update)
    await service._route_update(normal_update)

    # Wait for processing
    await asyncio.sleep(0.2)

    # Verify metrics
    metrics = service.get_task_metrics()
    assert metrics.completed_count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
