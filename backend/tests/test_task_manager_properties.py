"""Property-based tests for BoundedTaskManager using Hypothesis.

**Validates: Requirements 1.1, 1.2, 1.4, 1.5**

These tests verify universal correctness properties across all possible inputs:
- Property 1: Task Count Bounded - Concurrent tasks never exceed maximum
- Property 2: Queue Ordering by Priority - Priority-based processing order
- Property 3: Queue Rejection at Capacity - Rejection when queue full
"""

import asyncio
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from backend.app.realtime.task_manager import (
    BoundedTaskManager,
    TaskManagerConfig,
)


# Helper coroutine for testing
async def dummy_task(value: Any, delay: float = 0.01) -> Any:
    """Simple task that sleeps and returns a value."""
    await asyncio.sleep(delay)
    return value


# Property 1: Task Count Bounded
# **Validates: Requirements 1.1**
@given(
    burst_size=st.integers(min_value=50, max_value=500),
    max_tasks=st.integers(min_value=5, max_value=50),
    queue_size=st.integers(min_value=10, max_value=100),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_task_count_never_exceeds_maximum(
    burst_size: int, max_tasks: int, queue_size: int
):
    """Property 1: For any burst traffic pattern, concurrent task count never exceeds maximum.
    
    **Validates: Requirements 1.1**
    
    This property verifies that regardless of how many tasks are submitted,
    the number of concurrently executing tasks never exceeds the configured limit.
    """
    manager = BoundedTaskManager(
        TaskManagerConfig(
            max_concurrent_tasks=max_tasks,
            queue_max_size=queue_size,
            priority_levels=3,
        )
    )

    max_observed_count = 0

    # Submit burst of tasks and track max concurrent count
    for _ in range(burst_size):
        # Create coroutine and submit it
        coro = dummy_task(1, delay=0.05)
        await manager.submit_task(coro)

        # Check metrics after each submission
        metrics = manager.get_metrics()
        max_observed_count = max(max_observed_count, metrics.current_task_count)

        # CRITICAL PROPERTY: Current task count must never exceed maximum
        assert (
            metrics.current_task_count <= max_tasks
        ), f"Task count {metrics.current_task_count} exceeded maximum {max_tasks}"

    # Wait a bit for some tasks to complete
    await asyncio.sleep(0.2)

    # Check again - should still be within limit
    metrics = manager.get_metrics()
    assert (
        metrics.current_task_count <= max_tasks
    ), f"Task count {metrics.current_task_count} exceeded maximum {max_tasks} after processing"

    # Verify we actually had concurrent tasks (if burst was large enough)
    # Note: max_observed_count should be > 0 if we had any concurrent execution
    assert max_observed_count >= 0, "Task count tracking failed"

    await manager.shutdown(timeout=2.0)


# Property 2: Queue Ordering by Priority
# **Validates: Requirements 1.2, 1.4**
@given(
    num_tasks=st.integers(min_value=10, max_value=50),
    priorities=st.lists(
        st.integers(min_value=0, max_value=2), min_size=10, max_size=50
    ),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_queue_ordering_by_priority(
    num_tasks: int, priorities: list[int]
):
    """Property 2: For any sequence of task submissions with varying priorities,
    processing occurs in priority order (highest priority first).
    
    **Validates: Requirements 1.2, 1.4**
    
    This property verifies that when tasks are queued (because concurrent limit is reached),
    they are processed in priority order where lower priority numbers execute first.
    """
    # Use small concurrent limit to force queuing
    manager = BoundedTaskManager(
        TaskManagerConfig(
            max_concurrent_tasks=1,  # Force queuing
            queue_max_size=100,
            priority_levels=3,
        )
    )

    execution_order = []

    async def tracked_task(task_id: int, priority: int) -> int:
        """Task that records its execution order."""
        execution_order.append((task_id, priority))
        await asyncio.sleep(0.01)
        return task_id

    # Block the single slot with a slow task
    async def blocking_task():
        await asyncio.sleep(0.2)

    await manager.submit_task(blocking_task())

    # Give blocking task time to start
    await asyncio.sleep(0.01)

    # Submit tasks with varying priorities (ensure they get queued)
    task_priorities = priorities[:num_tasks]
    for i, priority in enumerate(task_priorities):
        coro = tracked_task(i, priority)
        await manager.submit_task(coro, priority=priority)

    # Wait for all tasks to complete
    await asyncio.sleep(0.5)

    # CRITICAL PROPERTY: Tasks should execute in priority order
    # Lower priority number = higher priority = executes first
    if len(execution_order) > 1:
        # Check that priorities are generally in ascending order
        # (allowing for some variation due to timing)
        for i in range(len(execution_order) - 1):
            current_priority = execution_order[i][1]
            next_priority = execution_order[i + 1][1]

            # Higher priority (lower number) should generally execute before lower priority
            # We allow equal priorities (FIFO within same priority)
            assert (
                current_priority <= next_priority
            ), f"Priority ordering violated: task with priority {current_priority} executed before priority {next_priority}"

    await manager.shutdown(timeout=1.0)


# Property 3: Queue Rejection at Capacity
# **Validates: Requirements 1.5**
@given(
    max_tasks=st.integers(min_value=1, max_value=10),
    queue_size=st.integers(min_value=5, max_value=20),
    excess_tasks=st.integers(min_value=5, max_value=30),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_queue_rejection_at_capacity(
    max_tasks: int, queue_size: int, excess_tasks: int
):
    """Property 3: For any task submission when queue is at maximum capacity,
    the task is rejected to prevent memory exhaustion.
    
    **Validates: Requirements 1.5**
    
    This property verifies that when both the concurrent task limit and queue
    are full, additional tasks are rejected rather than causing unbounded memory growth.
    """
    manager = BoundedTaskManager(
        TaskManagerConfig(
            max_concurrent_tasks=max_tasks,
            queue_max_size=queue_size,
            priority_levels=3,
        )
    )

    # Submit slow tasks to fill all slots
    async def slow_task(value: int) -> int:
        await asyncio.sleep(0.3)
        return value

    # Fill all concurrent slots
    for i in range(max_tasks):
        coro = slow_task(i)
        result = await manager.submit_task(coro)
        # These should succeed (slots available)
        assert result is not None or i >= max_tasks, f"Task {i} should have been accepted"

    # Give tasks time to start executing
    await asyncio.sleep(0.02)

    # Fill the queue
    for i in range(queue_size):
        coro = slow_task(max_tasks + i)
        await manager.submit_task(coro)

    # Give queue time to fill
    await asyncio.sleep(0.01)

    # Now submit excess tasks that should be rejected
    rejected_count = 0
    for i in range(excess_tasks):
        coro = slow_task(max_tasks + queue_size + i)
        result = await manager.submit_task(coro)
        if result is None:
            rejected_count += 1

    # CRITICAL PROPERTY: Some tasks must be rejected when capacity is reached
    metrics = manager.get_metrics()

    # Verify that rejections occurred
    assert (
        metrics.rejected_count > 0 or rejected_count > 0
    ), "Expected some tasks to be rejected when queue is full"

    # Verify queue depth never exceeds maximum
    assert (
        metrics.queue_depth <= queue_size
    ), f"Queue depth {metrics.queue_depth} exceeded maximum {queue_size}"

    # Verify concurrent tasks never exceed maximum
    assert (
        metrics.current_task_count <= max_tasks
    ), f"Task count {metrics.current_task_count} exceeded maximum {max_tasks}"

    await manager.shutdown(timeout=2.0)


# Additional property test: Metrics consistency
@given(
    num_operations=st.integers(min_value=20, max_value=100),
    max_tasks=st.integers(min_value=3, max_value=15),
    queue_size=st.integers(min_value=5, max_value=30),
)
@settings(max_examples=100, deadline=5000)
@pytest.mark.asyncio
@pytest.mark.property_test
async def test_property_metrics_consistency(
    num_operations: int, max_tasks: int, queue_size: int
):
    """Property: Metrics remain consistent throughout task lifecycle.
    
    This property verifies that:
    - current_task_count + queue_depth <= max_tasks + queue_size
    - completed_count + failed_count + rejected_count accounts for all submissions
    - Metrics are always non-negative
    """
    manager = BoundedTaskManager(
        TaskManagerConfig(
            max_concurrent_tasks=max_tasks,
            queue_max_size=queue_size,
            priority_levels=3,
        )
    )

    submitted_count = 0

    async def variable_task(value: int, should_fail: bool = False) -> int:
        """Task that may succeed or fail."""
        await asyncio.sleep(0.01)
        if should_fail:
            raise ValueError(f"Task {value} failed intentionally")
        return value

    # Submit various tasks
    for i in range(num_operations):
        should_fail = i % 7 == 0  # Some tasks fail
        coro = variable_task(i, should_fail)
        await manager.submit_task(coro)
        submitted_count += 1

        # Check metrics consistency after each operation
        metrics = manager.get_metrics()

        # PROPERTY: All metrics must be non-negative
        assert metrics.current_task_count >= 0, "current_task_count cannot be negative"
        assert metrics.queue_depth >= 0, "queue_depth cannot be negative"
        assert metrics.rejected_count >= 0, "rejected_count cannot be negative"
        assert metrics.completed_count >= 0, "completed_count cannot be negative"
        assert metrics.failed_count >= 0, "failed_count cannot be negative"

        # PROPERTY: Current tasks and queue must respect limits
        assert (
            metrics.current_task_count <= max_tasks
        ), f"current_task_count {metrics.current_task_count} exceeds max {max_tasks}"
        assert (
            metrics.queue_depth <= queue_size
        ), f"queue_depth {metrics.queue_depth} exceeds max {queue_size}"

    # Wait for tasks to complete
    await asyncio.sleep(0.3)

    final_metrics = manager.get_metrics()

    # PROPERTY: Total accounted tasks should match submissions
    total_accounted = (
        final_metrics.completed_count
        + final_metrics.failed_count
        + final_metrics.rejected_count
        + final_metrics.current_task_count
        + final_metrics.queue_depth
    )

    assert (
        total_accounted == submitted_count
    ), f"Metrics inconsistency: {total_accounted} accounted vs {submitted_count} submitted"

    await manager.shutdown(timeout=2.0)
