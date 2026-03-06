"""Unit tests for BoundedTaskManager."""

import asyncio

import pytest

from backend.app.realtime.task_manager import (
    BoundedTaskManager,
    TaskManagerConfig,
)


@pytest.mark.asyncio
async def test_immediate_execution_when_slots_available():
    """Test that tasks execute immediately when slots are available."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=2, queue_max_size=5, priority_levels=3)
    )

    results = []

    async def task(value: int):
        results.append(value)
        await asyncio.sleep(0.01)
        return value

    # Submit tasks when slots available
    task1 = await manager.submit_task(task(1))
    task2 = await manager.submit_task(task(2))

    assert task1 is not None
    assert task2 is not None

    await asyncio.gather(task1, task2)

    assert 1 in results
    assert 2 in results

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_task_queuing_when_slots_full():
    """Test that tasks are queued when concurrent limit is reached."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=2, queue_max_size=5, priority_levels=3)
    )

    results = []

    async def slow_task(value: int):
        await asyncio.sleep(0.1)
        results.append(value)
        return value

    # Fill all slots
    task1 = await manager.submit_task(slow_task(1))
    task2 = await manager.submit_task(slow_task(2))

    # These should be queued
    task3 = await manager.submit_task(slow_task(3))
    task4 = await manager.submit_task(slow_task(4))

    assert task1 is not None
    assert task2 is not None
    assert task3 is None  # Queued
    assert task4 is None  # Queued

    metrics = manager.get_metrics()
    assert metrics.queue_depth == 2

    # Wait for all tasks to complete
    await asyncio.sleep(0.3)

    assert len(results) == 4
    assert set(results) == {1, 2, 3, 4}

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_task_rejection_when_queue_full():
    """Test that tasks are rejected when queue is full."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=1, queue_max_size=2, priority_levels=3)
    )

    async def slow_task(value: int):
        await asyncio.sleep(0.2)
        return value

    # Fill the slot
    task1 = await manager.submit_task(slow_task(1))
    assert task1 is not None

    # Fill the queue
    task2 = await manager.submit_task(slow_task(2))
    task3 = await manager.submit_task(slow_task(3))
    assert task2 is None  # Queued
    assert task3 is None  # Queued

    # This should be rejected (queue full)
    task4 = await manager.submit_task(slow_task(4))
    assert task4 is None

    metrics = manager.get_metrics()
    assert metrics.queue_depth == 2
    assert metrics.rejected_count == 1

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_priority_ordering():
    """Test that higher priority tasks execute before lower priority tasks."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=1, queue_max_size=10, priority_levels=3)
    )

    results = []

    async def task(value: int):
        results.append(value)
        await asyncio.sleep(0.01)
        return value

    # Fill the slot with a slow task
    async def blocking_task():
        await asyncio.sleep(0.1)

    await manager.submit_task(blocking_task())

    # Queue tasks with different priorities
    await manager.submit_task(task(10), priority=2)  # Low priority
    await manager.submit_task(task(20), priority=0)  # High priority
    await manager.submit_task(task(30), priority=1)  # Normal priority
    await manager.submit_task(task(40), priority=0)  # High priority

    # Wait for all tasks to complete
    await asyncio.sleep(0.3)

    # High priority tasks should execute first
    assert results[0] == 20  # First high priority
    assert results[1] == 40  # Second high priority
    assert results[2] == 30  # Normal priority
    assert results[3] == 10  # Low priority

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_metrics_tracking():
    """Test that metrics are tracked correctly."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=2, queue_max_size=5, priority_levels=3)
    )

    async def task(value: int):
        await asyncio.sleep(0.05)
        return value

    async def failing_task():
        await asyncio.sleep(0.01)
        raise ValueError("Task failed")

    # Submit successful tasks
    await manager.submit_task(task(1))
    await manager.submit_task(task(2))

    # Submit failing task
    await manager.submit_task(failing_task())

    # Queue some tasks
    await manager.submit_task(task(3))
    await manager.submit_task(task(4))

    # Wait for tasks to complete
    await asyncio.sleep(0.2)

    metrics = manager.get_metrics()
    assert metrics.completed_count >= 2
    assert metrics.failed_count >= 1

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_graceful_shutdown():
    """Test graceful shutdown completes active tasks."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=2, queue_max_size=5, priority_levels=3)
    )

    results = []

    async def task(value: int):
        await asyncio.sleep(0.1)
        results.append(value)
        return value

    # Submit tasks
    await manager.submit_task(task(1))
    await manager.submit_task(task(2))
    await manager.submit_task(task(3))

    # Shutdown should wait for tasks to complete
    await manager.shutdown(timeout=1.0)

    # All tasks should have completed
    assert len(results) >= 2


@pytest.mark.asyncio
async def test_shutdown_rejects_new_tasks():
    """Test that new tasks are rejected during shutdown."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=2, queue_max_size=5, priority_levels=3)
    )

    async def task(value: int):
        await asyncio.sleep(0.05)
        return value

    # Start shutdown (don't await yet)
    shutdown_task = asyncio.create_task(manager.shutdown(timeout=1.0))

    # Give shutdown a moment to set the flag
    await asyncio.sleep(0.01)

    # Try to submit a task during shutdown
    result = await manager.submit_task(task(1))
    assert result is None

    metrics = manager.get_metrics()
    assert metrics.rejected_count >= 1

    await shutdown_task


@pytest.mark.asyncio
async def test_invalid_priority_uses_default():
    """Test that invalid priority values use default priority."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=1, queue_max_size=5, priority_levels=3)
    )

    results = []

    async def task(value: int):
        results.append(value)
        await asyncio.sleep(0.01)
        return value

    # Block the slot
    async def blocking_task():
        await asyncio.sleep(0.1)

    await manager.submit_task(blocking_task())

    # Submit with invalid priority (should use default priority 1)
    await manager.submit_task(task(1), priority=-1)
    await manager.submit_task(task(2), priority=10)

    # Wait for tasks to complete
    await asyncio.sleep(0.2)

    # Tasks should have executed (not rejected)
    assert len(results) == 2

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_concurrent_task_limit():
    """Test that concurrent task limit is enforced."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=3, queue_max_size=10, priority_levels=3)
    )

    active_count = 0
    max_active = 0

    async def task(value: int):
        nonlocal active_count, max_active
        active_count += 1
        max_active = max(max_active, active_count)
        await asyncio.sleep(0.05)
        active_count -= 1
        return value

    # Submit many tasks
    tasks = []
    for i in range(10):
        result = await manager.submit_task(task(i))
        if result is not None:
            tasks.append(result)

    # Wait for all tasks to complete
    await asyncio.sleep(0.3)

    # Max concurrent should not exceed limit
    assert max_active <= 3

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_queue_depth_metric():
    """Test that queue depth metric is accurate."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=1, queue_max_size=5, priority_levels=3)
    )

    async def slow_task():
        await asyncio.sleep(0.2)

    # Fill the slot
    await manager.submit_task(slow_task())

    # Give the task a moment to start executing
    await asyncio.sleep(0.01)

    # Queue tasks
    await manager.submit_task(slow_task())
    await manager.submit_task(slow_task())
    await manager.submit_task(slow_task())

    metrics = manager.get_metrics()
    assert metrics.queue_depth == 3
    assert metrics.current_task_count >= 1

    await manager.shutdown(timeout=1.0)


@pytest.mark.asyncio
async def test_fifo_ordering_within_same_priority():
    """Test that tasks with same priority execute in FIFO order."""
    manager = BoundedTaskManager(
        TaskManagerConfig(max_concurrent_tasks=1, queue_max_size=10, priority_levels=3)
    )

    results = []

    async def task(value: int):
        results.append(value)
        await asyncio.sleep(0.01)
        return value

    # Block the slot
    async def blocking_task():
        await asyncio.sleep(0.1)

    await manager.submit_task(blocking_task())

    # Queue tasks with same priority
    await manager.submit_task(task(1), priority=1)
    await manager.submit_task(task(2), priority=1)
    await manager.submit_task(task(3), priority=1)
    await manager.submit_task(task(4), priority=1)

    # Wait for all tasks to complete
    await asyncio.sleep(0.3)

    # Should execute in FIFO order
    assert results == [1, 2, 3, 4]

    await manager.shutdown(timeout=1.0)
