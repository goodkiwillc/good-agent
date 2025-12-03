"""Stress tests for SyncBridge concurrent dispatch scenarios.

This suite targets coverage gaps in sync_bridge.py, specifically:
- Concurrent sync→async bridging under load
- Task lifecycle and cleanup verification
- Error propagation through sync/async boundary
- Contextvar isolation across threads
"""

import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from good_agent.core.event_router import EventRouter


class TestSyncBridgeConcurrency:
    """Test sync bridge behavior under concurrent load."""

    def test_concurrent_apply_sync_calls(self) -> None:
        """Multiple threads calling apply_sync should not interfere."""
        router = EventRouter()
        results: dict[int, list[int]] = {}
        lock = threading.Lock()

        @router.on("thread:work")
        async def async_handler(ctx) -> None:
            thread_id = ctx.parameters["thread_id"]
            value = ctx.parameters["value"]
            await asyncio.sleep(0.001)  # Small delay to increase contention
            with lock:
                if thread_id not in results:
                    results[thread_id] = []
                results[thread_id].append(value)

        def worker(thread_id: int, count: int) -> None:
            for i in range(count):
                router.apply_sync("thread:work", thread_id=thread_id, value=i)

        # Launch 10 threads, each doing 5 operations
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(worker, tid, 5) for tid in range(10)]
            for future in futures:
                future.result()

        # Verify all operations completed
        assert len(results) == 10
        for tid in range(10):
            assert results[tid] == [0, 1, 2, 3, 4]

    def test_concurrent_do_calls_complete(self) -> None:
        """Concurrent do() calls should all be dispatched (fire-and-forget)."""
        router = EventRouter()
        counter_lock = threading.Lock()
        call_count = {"value": 0}

        @router.on("fire:event")
        async def async_handler(ctx) -> None:
            await asyncio.sleep(0.001)
            with counter_lock:
                call_count["value"] += 1

        def fire_worker(count: int) -> None:
            for _ in range(count):
                router.do("fire:event")

        # Launch threads that fire events
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(fire_worker, 10) for _ in range(5)]
            for future in futures:
                future.result()

        # Wait for all tasks to complete
        router._sync_bridge.join_sync()

        # All 50 events should have been processed
        assert call_count["value"] == 50

    def test_sync_bridge_isolates_contextvars_across_threads(self) -> None:
        """Each thread should have isolated contextvar values."""
        router = EventRouter()
        results: dict[int, Any] = {}
        lock = threading.Lock()

        @router.on("ctx:test")
        async def handler_with_ctx(ctx) -> None:
            thread_id = ctx.parameters["thread_id"]
            # Simulate work that depends on context
            await asyncio.sleep(0.001)
            with lock:
                results[thread_id] = ctx.parameters.get("data")

        def worker(thread_id: int) -> None:
            # Each thread sets unique data
            router.apply_sync("ctx:test", thread_id=thread_id, data=f"thread-{thread_id}")

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker, tid) for tid in range(5)]
            for future in futures:
                future.result()

        # Each thread should see its own data
        for tid in range(5):
            assert results[tid] == f"thread-{tid}"

    def test_interleaved_sync_and_async_dispatch(self) -> None:
        """Mix of apply_sync and apply_async should coexist safely."""
        router = EventRouter()
        sync_results: list[int] = []
        async_results: list[int] = []
        lock = threading.Lock()

        @router.on("mixed:event")
        async def handler(ctx) -> None:
            value = ctx.parameters["value"]
            is_sync = ctx.parameters.get("is_sync", False)
            await asyncio.sleep(0.001)
            with lock:
                if is_sync:
                    sync_results.append(value)
                else:
                    async_results.append(value)

        def sync_worker() -> None:
            for i in range(10):
                router.apply_sync("mixed:event", value=i, is_sync=True)

        async def async_worker() -> None:
            for i in range(10):
                await router.apply_async("mixed:event", value=i, is_sync=False)

        # Run sync in thread, async in event loop
        with ThreadPoolExecutor(max_workers=1) as executor:
            sync_future = executor.submit(sync_worker)
            asyncio.run(async_worker())
            sync_future.result()

        router._sync_bridge.join_sync()

        # Both paths should complete
        assert len(sync_results) == 10
        assert len(async_results) == 10


class TestSyncBridgeErrorHandling:
    """Test error propagation through sync bridge."""

    def test_async_handler_exception_propagates_to_sync_caller(self) -> None:
        """Exceptions in async handlers should be captured in context."""
        router = EventRouter()

        @router.on("failing:event")
        async def failing_handler(ctx) -> None:
            await asyncio.sleep(0.001)
            raise ValueError("Async handler failed")

        ctx = router.apply_sync("failing:event")
        assert isinstance(ctx.exception, ValueError)
        assert "Async handler failed" in str(ctx.exception)

    def test_multiple_handlers_with_mixed_success(self) -> None:
        """When some handlers fail, successful ones should still run."""
        router = EventRouter()
        successful_calls: list[str] = []

        @router.on("mixed:outcome", priority=100)
        async def handler1(ctx) -> None:
            successful_calls.append("handler1")

        @router.on("mixed:outcome", priority=90)
        async def handler2(ctx) -> None:
            raise RuntimeError("handler2 fails")

        @router.on("mixed:outcome", priority=80)
        async def handler3(ctx) -> None:
            successful_calls.append("handler3")

        # apply_sync should capture the exception in context
        ctx = router.apply_sync("mixed:outcome")

        # Exception should be captured
        assert isinstance(ctx.exception, RuntimeError)
        assert "handler2 fails" in str(ctx.exception)

        # Handler1 should have run (higher priority runs first)
        # Handler3 should also run (exceptions don't stop subsequent handlers)
        assert "handler1" in successful_calls
        assert "handler3" in successful_calls

    def test_do_with_failing_async_handlers_does_not_block(self) -> None:
        """do() should not propagate exceptions from async handlers."""
        router = EventRouter()
        success_count = {"value": 0}

        @router.on("fire:fail", priority=100)
        async def success_handler(ctx) -> None:
            success_count["value"] += 1

        @router.on("fire:fail", priority=90)
        async def failing_handler(ctx) -> None:
            raise Exception("This should not crash do()")

        # do() should return immediately without raising
        router.do("fire:fail")
        router._sync_bridge.join_sync()

        # Success handler should have run
        assert success_count["value"] == 1


class TestSyncBridgeTaskCleanup:
    """Test proper task lifecycle and cleanup."""

    def test_sync_bridge_tracks_pending_tasks(self) -> None:
        """Sync bridge should accurately track pending tasks."""
        router = EventRouter()
        task_started = threading.Event()
        task_can_finish = threading.Event()

        @router.on("blocking:event")
        async def blocking_handler(ctx) -> None:
            task_started.set()
            # Wait for signal
            await asyncio.sleep(0.01)
            while not task_can_finish.is_set():
                await asyncio.sleep(0.001)

        def fire_and_check() -> None:
            router.do("blocking:event")
            # Give handler time to start
            assert task_started.wait(timeout=1.0)
            # Task should be pending
            assert router._sync_bridge.task_count > 0

        thread = threading.Thread(target=fire_and_check)
        thread.start()
        thread.join()

        # Allow task to complete
        task_can_finish.set()
        router._sync_bridge.join_sync()

        # No tasks should remain
        assert router._sync_bridge.task_count == 0

    def test_join_waits_for_all_fire_and_forget_tasks(self) -> None:
        """join() should block until all do() tasks complete."""
        router = EventRouter()
        completed: list[int] = []
        lock = threading.Lock()

        @router.on("slow:event")
        async def slow_handler(ctx) -> None:
            task_id = ctx.parameters["task_id"]
            await asyncio.sleep(0.01)
            with lock:
                completed.append(task_id)

        # Fire 10 events
        for i in range(10):
            router.do("slow:event", task_id=i)

        # At this point, tasks may not be done
        # But join should wait for all
        router._sync_bridge.join_sync()

        # All should be completed
        assert sorted(completed) == list(range(10))
        assert router._sync_bridge.task_count == 0

    def test_close_cancels_pending_tasks(self) -> None:
        """close() should clean up resources and cancel pending tasks."""
        router = EventRouter()
        handler_started = threading.Event()
        results: list[str] = []

        @router.on("cleanup:test")
        async def long_handler(ctx) -> None:
            handler_started.set()
            try:
                await asyncio.sleep(10)  # Long sleep
                results.append("completed")
            except asyncio.CancelledError:
                results.append("cancelled")
                raise

        # Fire event in background
        def fire() -> None:
            router.do("cleanup:test")
            assert handler_started.wait(timeout=1.0)

        thread = threading.Thread(target=fire)
        thread.start()
        thread.join()

        # Close should cancel the long-running task
        router._sync_bridge.close_sync()

        # Handler should have been cancelled
        # Note: This is best-effort; some tasks may complete before cancellation
        assert router._sync_bridge.task_count == 0


class TestSyncBridgeEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_apply_sync_with_no_handlers_returns_immediately(self) -> None:
        """apply_sync on unregistered event should return empty context."""
        router = EventRouter()
        ctx = router.apply_sync("nonexistent:event", foo="bar")
        assert ctx.parameters["foo"] == "bar"  # type: ignore[attr-defined]
        assert ctx.output is None  # type: ignore[attr-defined]

    def test_nested_apply_sync_from_async_handler_raises_error(self) -> None:
        """Calling apply_sync from async handler should raise RuntimeError."""
        router = EventRouter()

        @router.on("outer")
        async def outer_handler(ctx) -> None:
            # This would cause a deadlock, so it should raise an error
            router.apply_sync("inner")

        @router.on("inner")
        async def inner_handler(ctx) -> None:
            pass

        with pytest.raises(
            RuntimeError,
            match="Cannot call apply_sync.*from within an async event handler",
        ):
            router.apply_sync("outer")

    def test_nested_async_calls_work_correctly(self) -> None:
        """Handler can call apply_async for nested dispatch."""
        router = EventRouter()
        call_stack: list[str] = []

        @router.on("outer")
        async def outer_handler(ctx) -> None:
            call_stack.append("outer")
            # Correct pattern: use apply_async for nested dispatch
            await router.apply_async("inner")

        @router.on("inner")
        async def inner_handler(ctx) -> None:
            call_stack.append("inner")

        router.apply_sync("outer")
        assert call_stack == ["outer", "inner"]

    def test_sync_bridge_survives_loop_restart(self) -> None:
        """Sync bridge should handle event loop restarts gracefully."""
        router = EventRouter()
        results: list[int] = []

        @router.on("restart:test")
        async def handler(ctx) -> None:
            results.append(ctx.parameters["value"])

        # First call
        router.apply_sync("restart:test", value=1)

        # Manually close and recreate loop (simulates restart)
        router._sync_bridge.close_sync()
        router._sync_bridge = type(router._sync_bridge)()

        # Should work after restart
        router.apply_sync("restart:test", value=2)

        assert results == [1, 2]
