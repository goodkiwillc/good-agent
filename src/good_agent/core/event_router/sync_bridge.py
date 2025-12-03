"""Async/sync compatibility bridge for event router.

This module provides the critical async/sync interoperability layer that allows
synchronous code to call async event handlers and vice versa. This is essential
for user-friendly APIs in interactive environments like Jupyter notebooks and
Python REPLs.

CONTENTS:
- SyncRequest: Queue-based coordination for sync->async calls
- SyncBridge: Manages event loop, thread pool, and task coordination
- Event loop lifecycle management
- Thread pool for async handler execution from sync contexts

THREAD SAFETY: All operations are thread-safe using threading.RLock and
asyncio's thread-safe methods (call_soon_threadsafe, run_coroutine_threadsafe).

CRITICAL: This module is foundational to UX. Do NOT simplify or remove
features without explicit user approval. Users MUST be able to call async
methods from sync contexts (e.g., Jupyter notebooks).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import queue
import threading
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from good_agent.core.event_router.protocols import EventName

logger = logging.getLogger(__name__)


@dataclass
class SyncRequest:
    """Request from sync context to async context.

    Used for queue-based coordination when sync code needs to call async
    handlers. The sync code creates a request, adds it to a queue, and waits
    for the async worker to process it and return the result via result_queue.

    Attributes:
        event: Event name to dispatch
        parameters: Event parameters as dict
        result_queue: Queue for async worker to return result
        request_id: Unique ID for debugging/tracing
    """

    event: EventName
    """Event name to dispatch."""

    parameters: dict[str, Any]
    """Event parameters."""

    result_queue: queue.Queue
    """Queue for returning result to sync caller."""

    request_id: str
    """Unique request ID for debugging."""


class SyncBridge:
    """Manages async/sync interoperability for the event router.

    This class handles the complex coordination needed to allow synchronous
    code to call async event handlers and vice versa. It manages:
    - Background event loop in dedicated thread
    - Thread pool for executing async handlers from sync context
    - Task tracking for cleanup and joining
    - contextvars propagation across async boundaries

    THREAD SAFETY: All public methods are thread-safe. Uses threading.RLock
    for state protection and asyncio's thread-safe methods for coordination.

    LIFECYCLE:
    1. Lazy initialization - event loop started on first async handler
    2. Task creation - background tasks tracked for cleanup
    3. Execution - sync/async handlers execute in appropriate contexts
    4. Cleanup - join() waits for tasks, close() shuts down resources

    UX IMPORTANCE: This enables "print(message.content)" instead of
    "await message.get_content()" in Jupyter notebooks and REPLs.
    """

    def __init__(self, debug: bool = False, default_timeout: float | None = None):
        """Initialize sync bridge.

        Args:
            debug: Enable debug logging for sync bridge operations
            default_timeout: Default timeout for sync->async operations (seconds)
        """
        self._debug = debug
        self._default_timeout = default_timeout

        # Thread safety
        self._lock = threading.RLock()
        """RLock for protecting bridge state."""

        # Event loop management
        self._event_loop: asyncio.AbstractEventLoop | None = None
        """Background event loop for async handler execution."""

        self._loop_thread: threading.Thread | None = None
        """Thread running the background event loop."""

        # Thread pool for async handlers from sync context
        self._thread_pool: concurrent.futures.ThreadPoolExecutor | None = None
        """Thread pool for running async handlers."""

        # Task tracking
        self._tasks: set[asyncio.Task] = set()
        """Active asyncio tasks for cleanup."""

        self._futures: set[concurrent.futures.Future] = set()
        """Active futures from run_coroutine_threadsafe."""

        # Queue-based sync->async bridge (optional, for advanced use)
        self._sync_request_queue: asyncio.Queue | None = None
        self._sync_worker_task: asyncio.Task | None = None

    def track_task(self, task: asyncio.Task) -> None:
        """Track externally created asyncio tasks for coordinated cleanup."""
        with self._lock:
            self._tasks.add(task)

        def _cleanup(done: asyncio.Task) -> None:
            self._tasks.discard(done)

        task.add_done_callback(_cleanup)

    def start_event_loop(self) -> None:
        """Start background event loop for async handlers.

        Creates a dedicated thread running an asyncio event loop. This loop
        is used to execute async event handlers when called from sync context.

        THREAD SAFETY: Protected by self._lock. Safe to call multiple times
        (will not create duplicate loops).

        PERFORMANCE: Loop startup takes ~10-50ms. Loop is reused across all
        async handler executions.
        """
        with self._lock:
            # Already started?
            if self._event_loop and not self._event_loop.is_closed():
                return

            def run_loop():
                """Thread target that runs the event loop forever."""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                self._event_loop = loop
                loop.run_forever()

            self._loop_thread = threading.Thread(
                target=run_loop, daemon=True, name="EventRouter-AsyncLoop"
            )
            self._loop_thread.start()

            # Wait for loop to start (with timeout to avoid hanging)
            timeout = time.time() + 5.0
            while not self._event_loop or not self._event_loop.is_running():
                if time.time() > timeout:
                    raise RuntimeError("Event loop failed to start within 5 seconds")
                threading.Event().wait(0.01)

            if self._debug:
                logger.debug(f"Started event loop in thread {self._loop_thread.name}")

    def run_coroutine_from_sync(self, coro: Any, timeout: float | None = None) -> Any:
        """Schedule ``coro`` on the bridge event loop and block until completion."""
        # Ensure event loop is running
        if not self._event_loop:
            self.start_event_loop()

        assert self._event_loop is not None

        # Schedule coroutine in event loop thread
        future = asyncio.run_coroutine_threadsafe(coro, self._event_loop)

        # Track future for cleanup
        with self._lock:
            self._futures.add(future)

        try:
            # Wait for result with timeout
            effective_timeout = timeout or self._default_timeout
            result = future.result(timeout=effective_timeout)
            return result
        finally:
            # Clean up future
            with self._lock:
                self._futures.discard(future)

    def create_background_task(self, coro: Any) -> asyncio.Task:
        """Create a background task for fire-and-forget execution.

        Used by EventRouter.do() for non-blocking event dispatch with async
        handlers. The task is tracked for cleanup via join() and close().

        Args:
            coro: Coroutine to run in background

        Returns:
            asyncio.Task that will execute the coroutine

        THREAD SAFETY: Thread-safe via call_soon_threadsafe()

        Example:
            ```python
            async def handle_event():
                await process_data()

            # Fire and forget:
            task = bridge.create_background_task(handle_event())
            # Returns immediately, handle_event runs in background
            ```
        """
        # Ensure event loop is running
        if not self._event_loop:
            self.start_event_loop()

        loop = self._event_loop
        if loop is None:
            raise RuntimeError("Event loop failed to initialize for background task")

        # Create task in event loop thread
        task_container = []

        def create_task() -> None:
            task = loop.create_task(coro)
            task_container.append(task)
            with self._lock:
                self._tasks.add(task)
            # Remove from tracking when done
            task.add_done_callback(lambda t: self._tasks.discard(t))

        loop.call_soon_threadsafe(create_task)

        # Wait briefly for task creation
        timeout = time.time() + 1.0
        while not task_container:
            if time.time() > timeout:
                raise RuntimeError("Task creation timed out")
            threading.Event().wait(0.001)

        if self._debug:
            logger.debug(f"Created background task: {task_container[0]}")

        return task_container[0]

    def join_sync(self, timeout: float = 5.0) -> None:
        """Wait for all background tasks to complete (synchronous).

        This method blocks until all background tasks created via
        create_background_task() complete or timeout is reached.

        Args:
            timeout: Maximum time to wait in seconds

        THREAD SAFETY: Thread-safe

        PERFORMANCE: Adds 10ms delay before waiting to handle race where
        join_sync() is called immediately after do().
        """
        # Small delay to handle race condition where join_sync() called immediately after do()
        time.sleep(0.01)

        with self._lock:
            if not self._tasks:
                return

        async def wait_for_tasks():
            """Wait for all tasks with timeout."""
            try:
                with self._lock:
                    tasks = list(self._tasks)
                if tasks:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True), timeout=timeout
                    )
            except TimeoutError:
                if self._debug:
                    logger.warning(f"Timeout waiting for {len(self._tasks)} tasks")

        if self._event_loop:
            future = asyncio.run_coroutine_threadsafe(wait_for_tasks(), self._event_loop)
            future.result()

    async def join(self, timeout: float = 5.0) -> None:
        """Wait for all background tasks to complete (asynchronous).

        Async version of join_sync(). Use when calling from async context.

        Args:
            timeout: Maximum time to wait in seconds
        """
        with self._lock:
            if not self._tasks:
                return

        try:
            with self._lock:
                tasks = list(self._tasks)
            await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=timeout)
        except TimeoutError:
            if self._debug:
                logger.warning(f"Timeout waiting for {len(self._tasks)} tasks")

    def close_sync(self) -> None:
        """Clean up all resources (synchronous).

        Stops event loop, cancels tasks, shuts down thread pool. Use when
        destroying the event router or in __exit__().

        THREAD SAFETY: Thread-safe
        """
        with self._lock:
            # Cancel any remaining futures first
            for future in list(self._futures):
                if not future.done():
                    future.cancel()
            self._futures.clear()

            # Cancel any remaining tasks and wait for them to be cancelled
            if self._tasks and self._event_loop:

                async def cancel_and_wait():
                    """Cancel all tasks and wait for them to finish."""
                    tasks_to_cancel = [t for t in list(self._tasks) if not t.done()]
                    for task in tasks_to_cancel:
                        task.cancel()
                    # Wait for all cancelled tasks to complete
                    if tasks_to_cancel:
                        await asyncio.gather(*tasks_to_cancel, return_exceptions=True)

                try:
                    future = asyncio.run_coroutine_threadsafe(cancel_and_wait(), self._event_loop)
                    future.result(timeout=1.0)
                except Exception:
                    # Best effort - continue with shutdown
                    pass

            # Now stop event loop
            if self._event_loop:
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)
                # Give loop time to process stop request
                time.sleep(0.1)
                if self._loop_thread:
                    self._loop_thread.join(timeout=1.0)

            # Shutdown thread pool
            if self._thread_pool:
                self._thread_pool.shutdown(wait=False)

            if self._debug:
                logger.debug("Sync bridge closed")

    async def close(self) -> None:
        """Clean up all resources (asynchronous).

        Async version of close_sync(). Use when calling from async context.
        """
        with self._lock:
            # Wait for all tasks to complete
            await self.join(timeout=1.0)

            # Cancel any remaining futures
            for future in list(self._futures):
                if not future.done():
                    future.cancel()
            self._futures.clear()

            # Cancel any remaining tasks
            if self._tasks:
                for task in list(self._tasks):
                    if not task.done():
                        task.cancel()
                # Give tasks a chance to handle cancellation
                await asyncio.sleep(0.1)

            # Stop event loop if needed
            if self._event_loop and self._event_loop != asyncio.get_running_loop():
                self._event_loop.call_soon_threadsafe(self._event_loop.stop)

            # Shutdown thread pool
            if self._thread_pool:
                self._thread_pool.shutdown(wait=False)

            if self._debug:
                logger.debug("Sync bridge closed (async)")

    @property
    def task_count(self) -> int:
        """Get number of active background tasks.

        Returns:
            Number of tasks currently running
        """
        with self._lock:
            return len(self._tasks)

    @property
    def has_event_loop(self) -> bool:
        """Check if event loop is running.

        Returns:
            True if event loop is active
        """
        with self._lock:
            return self._event_loop is not None and self._event_loop.is_running()

    @property
    def is_event_loop_thread(self) -> bool:
        """Check if current thread is the event loop thread.

        Returns:
            True if calling thread is the event loop thread
        """
        with self._lock:
            return self._loop_thread is not None and threading.current_thread() == self._loop_thread
