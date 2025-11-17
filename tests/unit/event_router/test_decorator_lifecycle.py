"""Tests for @emit decorator lifecycle phases and edge cases.

This suite targets coverage gaps in decorators.py, specifically:
- ERROR and FINALLY phases
- Custom event names vs method names
- include_args/include_result variations
- @emit without parentheses
- Error recovery paths
"""

import pytest

from good_agent.core.event_router import EventRouter
from good_agent.core.event_router.decorators import emit, emit_event
from good_agent.core.event_router.registration import LifecyclePhase


class TestEmitLifecyclePhases:
    """Test various lifecycle phase combinations."""

    def test_emit_error_phase_captures_exceptions(self) -> None:
        """@emit with ERROR phase should emit error events when method raises."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.error_events: list[dict] = []

            @emit("process", phases=LifecyclePhase.ERROR)
            def failing_method(self, value: int) -> int:
                raise ValueError(f"Failed with {value}")

        router = TestRouter()

        # Register handler for error event
        @router.on("process:error")
        def handle_error(ctx) -> None:
            router.error_events.append(dict(ctx.parameters))

        # Execute method and expect error
        with pytest.raises(ValueError, match="Failed with 42"):
            router.failing_method(42)

        # Verify error event was emitted
        assert len(router.error_events) == 1
        assert router.error_events[0]["value"] == 42
        assert isinstance(router.error_events[0]["error"], ValueError)

    @pytest.mark.asyncio
    async def test_emit_error_phase_async(self) -> None:
        """@emit with ERROR phase works with async methods."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.error_events: list[dict] = []

            @emit("async_process", phases=LifecyclePhase.ERROR)
            async def failing_async_method(self, value: int) -> int:
                raise RuntimeError(f"Async failed with {value}")

        router = TestRouter()

        @router.on("async_process:error")
        async def handle_error(ctx) -> None:
            router.error_events.append(dict(ctx.parameters))

        with pytest.raises(RuntimeError, match="Async failed with 123"):
            await router.failing_async_method(123)

        assert len(router.error_events) == 1
        assert router.error_events[0]["value"] == 123

    def test_emit_finally_phase_always_executes(self) -> None:
        """@emit with FINALLY phase executes on both success and failure."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.finally_events: list[dict] = []

            @emit("operation", phases=LifecyclePhase.FINALLY)
            def method_with_finally(self, should_fail: bool) -> str:
                if should_fail:
                    raise ValueError("Intentional failure")
                return "success"

        router = TestRouter()

        @router.on("operation:finally")
        def handle_finally(ctx) -> None:
            router.finally_events.append(dict(ctx.parameters))

        # Success case
        result = router.method_with_finally(False)
        assert result == "success"
        assert len(router.finally_events) == 1
        assert router.finally_events[0]["result"] == "success"
        assert "error" not in router.finally_events[0]

        # Failure case
        with pytest.raises(ValueError):
            router.method_with_finally(True)

        assert len(router.finally_events) == 2
        assert isinstance(router.finally_events[1]["error"], ValueError)

    @pytest.mark.asyncio
    async def test_emit_finally_phase_async(self) -> None:
        """@emit FINALLY phase works with async methods."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.finally_count = 0

            @emit("async_op", phases=LifecyclePhase.FINALLY)
            async def async_with_finally(self, should_fail: bool) -> str:
                if should_fail:
                    raise RuntimeError("Async failure")
                return "async_success"

        router = TestRouter()

        @router.on("async_op:finally")
        async def handle_finally(ctx) -> None:
            router.finally_count += 1

        # Success
        result = await router.async_with_finally(False)
        assert result == "async_success"
        assert router.finally_count == 1

        # Failure
        with pytest.raises(RuntimeError):
            await router.async_with_finally(True)
        assert router.finally_count == 2

    def test_emit_combined_phases(self) -> None:
        """@emit can combine multiple phases with bitwise OR."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.events: list[str] = []

            @emit(
                "combined",
                phases=LifecyclePhase.BEFORE
                | LifecyclePhase.AFTER
                | LifecyclePhase.ERROR
                | LifecyclePhase.FINALLY,
            )
            def tracked_method(self, should_fail: bool = False) -> str:
                if should_fail:
                    raise ValueError("Test error")
                return "done"

        router = TestRouter()

        # Register handlers for all phases
        @router.on("combined:before")
        def track_before(ctx) -> None:
            router.events.append("before")

        @router.on("combined:after")
        def track_after(ctx) -> None:
            router.events.append("after")

        @router.on("combined:error")
        def track_error(ctx) -> None:
            router.events.append("error")

        @router.on("combined:finally")
        def track_finally(ctx) -> None:
            router.events.append("finally")

        # Success path
        router.tracked_method(False)
        assert router.events == ["before", "after", "finally"]

        # Failure path
        router.events.clear()
        with pytest.raises(ValueError):
            router.tracked_method(True)
        assert router.events == ["before", "error", "finally"]

    def test_emit_error_phase_can_return_value(self) -> None:
        """ERROR phase handler can provide recovery value via ctx.stop()."""

        class TestRouter(EventRouter):
            @emit("recoverable", phases=LifecyclePhase.ERROR)
            def method_with_recovery(self, value: int) -> int:
                if value < 0:
                    raise ValueError("Negative value")
                return value

        router = TestRouter()

        @router.on("recoverable:error")
        def recover_from_error(ctx) -> None:
            # Provide recovery value
            ctx.stop(output=0)

        # Normal case
        assert router.method_with_recovery(42) == 42

        # Recovery case - error handler should provide recovery value
        # Note: This tests that the emit decorator handles ctx.stop() output
        result = router.method_with_recovery(-1)
        # If recovery works, result should be 0; otherwise ValueError will be raised
        assert result == 0  # Recovery value from error handler


class TestEmitConfiguration:
    """Test @emit decorator configuration options."""

    def test_emit_uses_method_name_as_default_event(self) -> None:
        """@emit without event name should use method name."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.event_names: list[str] = []

            @emit(LifecyclePhase.BEFORE, event=None)
            def my_method(self) -> None:
                pass

        router = TestRouter()

        @router.on("my_method:before")
        def capture_event(ctx) -> None:
            router.event_names.append(ctx.event)

        router.my_method()
        router._sync_bridge.join()
        assert router.event_names == ["my_method:before"]

    def test_emit_custom_event_name(self) -> None:
        """@emit with custom event name overrides method name."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.event_names: list[str] = []

            @emit("custom_event", phases=LifecyclePhase.BEFORE)
            def some_method(self) -> None:
                pass

        router = TestRouter()

        @router.on("custom_event:before")
        def capture_event(ctx) -> None:
            router.event_names.append(ctx.event)

        router.some_method()
        router._sync_bridge.join()
        assert router.event_names == ["custom_event:before"]

    def test_emit_include_args_false(self) -> None:
        """@emit with include_args=False should not include arguments."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.event_params: list[dict] = []

            @emit("process", phases=LifecyclePhase.BEFORE, include_args=False)
            def method_with_args(self, x: int, y: int) -> int:
                return x + y

        router = TestRouter()

        @router.on("process:before")
        def capture_params(ctx) -> None:
            router.event_params.append(dict(ctx.parameters))

        router.method_with_args(10, 20)
        # Parameters should be empty when include_args=False
        assert router.event_params[0] == {}

    def test_emit_include_result_false(self) -> None:
        """@emit with include_result=False should not include result."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.event_params: list[dict] = []

            @emit("process", phases=LifecyclePhase.AFTER, include_result=False)
            def method_with_result(self, x: int) -> int:
                return x * 2

        router = TestRouter()

        @router.on("process:after")
        def capture_params(ctx) -> None:
            router.event_params.append(dict(ctx.parameters))

        router.method_with_result(5)
        # Result should not be in parameters
        assert "result" not in router.event_params[0]
        assert router.event_params[0]["x"] == 5

    def test_emit_without_parentheses(self) -> None:
        """@emit without parentheses should work with default phases."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.events: list[str] = []

            @emit  # type: ignore[arg-type]
            def simple_method(self, value: int) -> int:
                return value * 2

        router = TestRouter()

        @router.on("simple_method:before")
        def track_before(ctx) -> None:
            router.events.append("before")

        @router.on("simple_method:after")
        def track_after(ctx) -> None:
            router.events.append("after")

        result = router.simple_method(5)  # type: ignore[type-var]
        assert result == 10
        router._sync_bridge.join()
        assert router.events == ["before", "after"]


class TestEmitEdgeCases:
    """Test edge cases and error paths in @emit decorator."""

    def test_emit_on_non_event_router_instance(self) -> None:
        """@emit on non-EventRouter class should not interfere."""

        class PlainClass:
            @emit("test")  # type: ignore[misc]
            def method(self, x: int) -> int:
                return x * 2

        obj = PlainClass()
        # Should work normally without event routing
        assert obj.method(5) == 10

    @pytest.mark.asyncio
    async def test_emit_on_non_event_router_async(self) -> None:
        """@emit on non-EventRouter async method should not interfere."""

        class PlainClass:
            @emit("test")  # type: ignore[misc]
            async def async_method(self, x: int) -> int:
                return x * 2

        obj = PlainClass()
        result = await obj.async_method(5)
        assert result == 10

    def test_emit_event_backward_compatibility(self) -> None:
        """emit_event() function provides backward compatibility."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.events: list[str] = []

            @emit_event("legacy", phases=LifecyclePhase.BEFORE | LifecyclePhase.AFTER)
            def legacy_method(self, value: int) -> int:
                return value

        router = TestRouter()

        @router.on("legacy:before")
        def track_before(ctx) -> None:
            router.events.append(ctx.event)

        @router.on("legacy:after")
        def track_after(ctx) -> None:
            router.events.append(ctx.event)

        router.legacy_method(42)
        router._sync_bridge.join()
        assert "legacy:before" in router.events
        assert "legacy:after" in router.events

    def test_emit_with_list_phases(self) -> None:
        """@emit should support phases as a list for compatibility."""

        class TestRouter(EventRouter):
            def __init__(self):
                super().__init__()
                self.events: list[str] = []

            @emit("test", phases=[LifecyclePhase.BEFORE, LifecyclePhase.AFTER])
            def method(self) -> str:
                return "test"

        router = TestRouter()

        @router.on("test:before")
        def track_before(ctx) -> None:
            router.events.append("before")

        @router.on("test:after")
        def track_after(ctx) -> None:
            router.events.append("after")

        router.method()
        router._sync_bridge.join()
        assert router.events == ["before", "after"]

    def test_emit_after_can_transform_result(self) -> None:
        """AFTER phase handler can transform result via ctx.stop()."""

        class TestRouter(EventRouter):
            @emit("transform", phases=LifecyclePhase.AFTER)
            def get_value(self) -> int:
                return 10

        router = TestRouter()

        @router.on("transform:after")
        def double_result(ctx) -> None:
            original = ctx.parameters["result"]
            ctx.stop(output=original * 2)

        result = router.get_value()
        router._sync_bridge.join()
        # The emit decorator checks ctx.output and uses it if not None
        assert result == 20  # Transformed by handler

    @pytest.mark.asyncio
    async def test_emit_after_transforms_async_result(self) -> None:
        """AFTER phase handler can transform async result."""

        class TestRouter(EventRouter):
            @emit("async_transform", phases=LifecyclePhase.AFTER)
            async def get_async_value(self) -> int:
                return 5

        router = TestRouter()

        @router.on("async_transform:after")
        async def triple_result(ctx) -> None:
            original = ctx.parameters["result"]
            ctx.stop(output=original * 3)

        result = await router.get_async_value()
        assert result == 15
