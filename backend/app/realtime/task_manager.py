"""Bounded async task manager to prevent memory exhaustion during burst traffic."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TaskManagerConfig:
    """Configuration for BoundedTaskManager."""
    max_concurrent_tasks: int = 100
    queue_max_size: int = 1000
    priority_levels: int = 3


@dataclass
class TaskMetrics:
    """Metrics for task manager monitoring."""
    current_task_count: int = 0
    queue_depth: int = 0
    rejected_count: int = 0
    completed_count: int = 0
    failed_count: int = 0


class BoundedTaskManager:
    """Manages async task execution with bounded concurrency and priority queuing.
    
    Key features:
    - Limits concurrent tasks using asyncio.Semaphore
    - Queues excess tasks in priority queue (lower priority number = higher priority)
    - Rejects tasks when queue is full to prevent memory exhaustion
    - Tracks metrics for monitoring (current tasks, queue depth, rejections)
    - Graceful shutdown with timeout
    
    Priority levels:
    - 0: Highest priority (critical tasks)
    - 1: Normal priority (default)
    - 2+: Lower priority
    """

    def __init__(self, config: TaskManagerConfig):
        """Initialize task manager with configuration.
        
        Args:
            config: Configuration with max_concurrent_tasks, queue_max_size, priority_levels
        """
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent_tasks)

        # Priority queue: (priority, counter, coroutine)
        # counter ensures FIFO ordering within same priority
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue(
            maxsize=config.queue_max_size
        )

        # Metrics tracking
        self._current_task_count = 0
        self._rejected_count = 0
        self._completed_count = 0
        self._failed_count = 0
        self._task_counter = 0  # For FIFO ordering within priority

        # Active tasks for shutdown
        self._active_tasks: set[asyncio.Task] = set()

        # Queue processor task
        self._processor_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

        # Start queue processor
        self._start_processor()

    def _start_processor(self) -> None:
        """Start background task to process queued tasks."""
        if self._processor_task is None or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_queue())

    async def _process_queue(self) -> None:
        """Background task that processes queued tasks when slots become available."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for a task slot to become available
                await self.semaphore.acquire()

                try:
                    # Get next task from queue (with timeout to check shutdown)
                    priority, counter, coro = await asyncio.wait_for(
                        self.task_queue.get(),
                        timeout=0.1
                    )

                    # Execute the task
                    task = asyncio.create_task(self._execute_task(coro))
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)

                except TimeoutError:
                    # No task in queue, release semaphore and continue
                    self.semaphore.release()
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in queue processor: {e}")
                await asyncio.sleep(0.1)

    async def _execute_task(self, coro: Coroutine) -> Any:
        """Execute a task and track metrics.
        
        Args:
            coro: Coroutine to execute
            
        Returns:
            Result of the coroutine
        """
        self._current_task_count += 1
        try:
            result = await coro
            self._completed_count += 1
            return result
        except Exception as e:
            self._failed_count += 1
            logger.error(f"Task execution failed: {e}")
            raise
        finally:
            self._current_task_count -= 1
            self.semaphore.release()

    async def submit_task(
        self,
        coro: Coroutine,
        priority: int = 1
    ) -> asyncio.Task | None:
        """Submit task for execution. Returns None if queue full.
        
        If a task slot is available, the task executes immediately.
        Otherwise, it's queued for later execution.
        If the queue is full, the task is rejected and None is returned.
        
        Args:
            coro: Coroutine to execute
            priority: Priority level (0 = highest, default = 1)
            
        Returns:
            asyncio.Task if submitted successfully, None if rejected
        """
        if self._shutdown_event.is_set():
            logger.warning("Cannot submit task: manager is shutting down")
            self._rejected_count += 1
            self._close_coro(coro)
            return None

        # Validate priority
        if priority < 0 or priority >= self.config.priority_levels:
            logger.warning(f"Invalid priority {priority}, using default priority 1")
            priority = 1

        # Try to acquire semaphore immediately (non-blocking)
        if self.semaphore.locked():
            # No slots available, try to queue
            try:
                # Use put_nowait to avoid blocking
                self._task_counter += 1
                self.task_queue.put_nowait((priority, self._task_counter, coro))
                logger.debug(f"Task queued with priority {priority}, queue depth: {self.task_queue.qsize()}")
                return None  # Task queued, will execute later
            except asyncio.QueueFull:
                # Queue is full, reject task
                self._rejected_count += 1
                logger.warning(f"Task rejected: queue full (max size: {self.config.queue_max_size})")
                self._close_coro(coro)
                return None
        else:
            # Slot available, execute immediately
            await self.semaphore.acquire()
            task = asyncio.create_task(self._execute_task(coro))
            self._active_tasks.add(task)
            task.add_done_callback(self._active_tasks.discard)
            return task

    def get_metrics(self) -> TaskMetrics:
        """Return current task count, queue depth, rejected count.
        
        Returns:
            TaskMetrics with current statistics
        """
        return TaskMetrics(
            current_task_count=self._current_task_count,
            queue_depth=self.task_queue.qsize(),
            rejected_count=self._rejected_count,
            completed_count=self._completed_count,
            failed_count=self._failed_count
        )

    async def shutdown(self, timeout: float = 30.0) -> None:
        """Gracefully shutdown, completing queued tasks.
        
        This method:
        1. Sets shutdown flag to reject new tasks
        2. Waits for active tasks to complete (up to timeout)
        3. Cancels queue processor
        4. Drains remaining queued tasks
        
        Args:
            timeout: Maximum time to wait for tasks to complete (seconds)
        """
        logger.info("Initiating task manager shutdown...")

        # Set shutdown flag to reject new submissions
        self._shutdown_event.set()

        # Cancel queue processor
        if self._processor_task and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass

        # Wait for active tasks to complete (with timeout)
        if self._active_tasks:
            logger.info(f"Waiting for {len(self._active_tasks)} active tasks to complete...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks, return_exceptions=True),
                    timeout=timeout
                )
                logger.info("All active tasks completed")
            except TimeoutError:
                logger.warning(f"Shutdown timeout reached, cancelling {len(self._active_tasks)} remaining tasks")
                for task in self._active_tasks:
                    if not task.done():
                        task.cancel()

        # Drain remaining queued tasks
        queued_count = self.task_queue.qsize()
        if queued_count > 0:
            logger.warning(f"Discarding {queued_count} queued tasks during shutdown")
            while not self.task_queue.empty():
                try:
                    _, _, queued_coro = self.task_queue.get_nowait()
                    self._close_coro(queued_coro)
                except asyncio.QueueEmpty:
                    break

        logger.info("Task manager shutdown complete")

    @staticmethod
    def _close_coro(coro: Coroutine) -> None:
        """Close discarded coroutine objects to avoid RuntimeWarning noise."""
        try:
            coro.close()
        except Exception:
            pass
