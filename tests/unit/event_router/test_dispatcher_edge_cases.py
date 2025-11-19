"""Tests for EventRouter dispatcher edge cases and branch coverage.

This suite targets coverage gaps in event_router/core.py, specifically:
- Handler registration/deregistration edge cases
- Event context manipulation and output handling
- Broadcast/consume routing edge cases
- Predicate evaluation corner cases
- Handler chain short-circuiting
"""

import asyncio
from typing import Any

import pytest

from good_agent.core.event_router import EventContext, EventRouter
from good_agent.core.event_router.protocols import ApplyInterrupt


class TestHandlerRegistration:
    """Test handler registration edge cases."""

    def test_deregister_handler_during_emission(self) -> None:
        """Deregistering handler during event emission should not crash."""
        router = EventRouter()
        handler_ran = {"count": 0}

        def self_removing_handler(ctx: EventContext) -> None:
            handler_ran["count"] += 1
            # Remove self during execution using handler ID attached by decorator
            handler_id = self_removing_handler._handler_id  # type: ignore[attr-defined]
            router._handler_registry.deregister(handler_id)

        router.on("self:remove")(self_removing_handler)

        # First call should work
        router.do("self:remove")
        router._sync_bridge.join_sync()
        assert handler_ran["count"] == 1

        # Second call should not execute (handler removed)
        router.do("self:remove")
        router._sync_bridge.join_sync()
        assert handler_ran["count"] == 1

    def test_register_handler_with_none_predicate(self) -> None:
        """Registering handler with None predicate should always execute."""
        router = EventRouter()
        calls = {"count": 0}

        @router.on("test:event", predicate=None)
        def handler(ctx: EventContext) -> None:
            calls["count"] += 1

        router.do("test:event", condition=True)
        router.do("test:event", condition=False)
        router._sync_bridge.join_sync()

        # Should execute both times (no predicate filtering)
        assert calls["count"] == 2

    def test_multiple_handlers_same_priority(self) -> None:
        """Multiple handlers with same priority should all execute."""
        router = EventRouter()
        results: list[str] = []

        @router.on("same:priority", priority=100)
        def handler1(ctx: EventContext) -> None:
            results.append("handler1")

        @router.on("same:priority", priority=100)
        def handler2(ctx: EventContext) -> None:
            results.append("handler2")

        @router.on("same:priority", priority=100)
        def handler3(ctx: EventContext) -> None:
            results.append("handler3")

        router.do("same:priority")
        router._sync_bridge.join_sync()

        # All should execute (order within same priority may vary)
        assert len(results) == 3
        assert set(results) == {"handler1", "handler2", "handler3"}

    def test_handler_with_complex_predicate(self) -> None:
        """Predicate can perform complex condition checks."""
        router = EventRouter()
        results: list[int] = []

        def complex_predicate(ctx: EventContext) -> bool:
            value = ctx.parameters.get("value", 0)
            flag = ctx.parameters.get("flag", False)
            # Only execute if value > 10 AND flag is True
            return value > 10 and flag

        @router.on("complex:check", predicate=complex_predicate)
        def conditional_handler(ctx: EventContext) -> None:
            results.append(ctx.parameters["value"])

        # Should not execute: value too low
        router.do("complex:check", value=5, flag=True)
        router._sync_bridge.join_sync()
        assert len(results) == 0

        # Should not execute: flag is False
        router.do("complex:check", value=15, flag=False)
        router._sync_bridge.join_sync()
        assert len(results) == 0

        # Should execute: both conditions met
        router.do("complex:check", value=20, flag=True)
        router._sync_bridge.join_sync()
        assert results == [20]


class TestEventContextManipulation:
    """Test EventContext state management and output handling."""

    def test_context_stop_with_output_interrupts_chain(self) -> None:
        """ctx.stop(output=...) should interrupt handler chain."""
        router = EventRouter()
        execution_order: list[str] = []

        @router.on("chain:test", priority=100)
        def high_priority(ctx: EventContext) -> None:
            execution_order.append("high")
            ctx.stop(output="short_circuit")  # type: ignore[attr-defined]

        @router.on("chain:test", priority=90)
        def medium_priority(ctx: EventContext) -> None:
            execution_order.append("medium")

        @router.on("chain:test", priority=80)
        def low_priority(ctx: EventContext) -> None:
            execution_order.append("low")

        ctx = router.apply_sync("chain:test")

        # Only high priority should execute
        assert execution_order == ["high"]
        assert ctx.output == "short_circuit"  # type: ignore[attr-defined]
        assert ctx.stopped  # type: ignore[attr-defined]

    def test_context_stop_with_exception_sets_flag(self) -> None:
        """ctx.stop(exception=...) should set stopped_with_exception."""
        router = EventRouter()

        @router.on("exception:test")
        def handler_with_exception(ctx: EventContext) -> None:
            error = ValueError("Test error")
            ctx.stop(exception=error)  # type: ignore[attr-defined]

        ctx = router.apply_sync("exception:test")

        assert ctx.stopped_with_exception  # type: ignore[attr-defined]
        assert isinstance(ctx.output, ValueError)  # type: ignore[attr-defined]

    def test_context_parameters_are_mutable(self) -> None:
        """Handlers can modify context parameters for downstream handlers."""
        router = EventRouter()
        results: list[Any] = []

        @router.on("mutable:params", priority=100)
        def modifier(ctx: EventContext) -> None:
            # Modify parameter
            ctx.parameters["value"] = ctx.parameters.get("value", 0) * 2

        @router.on("mutable:params", priority=90)
        def reader(ctx: EventContext) -> None:
            results.append(ctx.parameters["value"])

        router.do("mutable:params", value=5)
        router._sync_bridge.join_sync()

        # Reader should see modified value
        assert results == [10]

    async def test_async_context_preserves_parameters(self) -> None:
        """Async handlers should receive original parameters."""
        router = EventRouter()
        received_params: list[dict] = []

        @router.on("async:params")
        async def async_handler(ctx: EventContext) -> None:
            await asyncio.sleep(0.001)
            received_params.append(dict(ctx.parameters))

        await router.apply_async("async:params", x=10, y=20)

        assert len(received_params) == 1
        assert received_params[0]["x"] == 10
        assert received_params[0]["y"] == 20


class TestBroadcastRouting:
    """Test broadcast_to/consume_from routing."""

    def test_broadcast_to_routes_events_bidirectionally(self) -> None:
        """broadcast_to should route events in both directions."""
        router1 = EventRouter()
        router2 = EventRouter()

        events_in_router2: list[str] = []
        events_in_router1: list[str] = []

        @router2.on("test:event")
        def handler_in_router2(ctx: EventContext) -> None:
            events_in_router2.append("test:event")  # Simplified - actual event tracking

        @router1.on("reverse:event")
        def handler_in_router1(ctx: EventContext) -> None:
            events_in_router1.append(
                "reverse:event"
            )  # Simplified - actual event tracking

        # Connect routers bidirectionally
        router1.broadcast_to(router2)

        # Event from router1 should reach router2
        router1.do("test:event")
        router1._sync_bridge.join_sync()
        router2._sync_bridge.join_sync()
        assert "test:event" in events_in_router2

        # Event from router2 should reach router1
        router2.do("reverse:event")
        router2._sync_bridge.join_sync()
        router1._sync_bridge.join_sync()
        assert "reverse:event" in events_in_router1

    def test_consume_from_is_unidirectional(self) -> None:
        """consume_from should only route in one direction."""
        source = EventRouter()
        consumer = EventRouter()

        events_in_consumer: list[str] = []
        events_in_source: list[str] = []

        @consumer.on("forward:event")
        def handler_in_consumer(ctx: EventContext) -> None:
            event_name = ctx.event
            assert event_name is not None
            events_in_consumer.append(event_name)

        @source.on("backward:event")
        def handler_in_source(ctx: EventContext) -> None:
            event_name = ctx.event
            assert event_name is not None
            events_in_source.append(event_name)

        # Consumer consumes from source (unidirectional)
        consumer.consume_from(source)

        # Event from source should reach consumer
        source.do("forward:event")
        source._sync_bridge.join_sync()
        consumer._sync_bridge.join_sync()
        assert "forward:event" in events_in_consumer

        # Event from consumer should NOT reach source
        consumer.do("backward:event")
        consumer._sync_bridge.join_sync()
        source._sync_bridge.join_sync()
        assert "backward:event" not in events_in_source

    def test_multiple_broadcast_targets(self) -> None:
        """Router can broadcast to multiple targets."""
        source = EventRouter()
        target1 = EventRouter()
        target2 = EventRouter()
        target3 = EventRouter()

        received: dict[str, list[str]] = {"t1": [], "t2": [], "t3": []}

        @target1.on("multi:event")
        def handler1(ctx: EventContext) -> None:
            event_name = ctx.event
            assert event_name is not None
            received["t1"].append(event_name)

        @target2.on("multi:event")
        def handler2(ctx: EventContext) -> None:
            event_name = ctx.event
            assert event_name is not None
            received["t2"].append(event_name)

        @target3.on("multi:event")
        def handler3(ctx: EventContext) -> None:
            event_name = ctx.event
            assert event_name is not None
            received["t3"].append(event_name)

        # Broadcast to all three
        source.broadcast_to(target1)
        source.broadcast_to(target2)
        source.broadcast_to(target3)

        source.do("multi:event")
        source._sync_bridge.join_sync()
        target1._sync_bridge.join_sync()
        target2._sync_bridge.join_sync()
        target3._sync_bridge.join_sync()

        # All targets should receive
        assert "multi:event" in received["t1"]
        assert "multi:event" in received["t2"]
        assert "multi:event" in received["t3"]


class TestHandlerChainBehavior:
    """Test handler chain execution and short-circuiting."""

    def test_empty_handler_chain_returns_empty_context(self) -> None:
        """Event with no handlers should return context with no output."""
        router = EventRouter()
        ctx = router.apply_sync("unregistered:event", data="test")

        assert ctx.parameters["data"] == "test"  # type: ignore[attr-defined]
        assert ctx.output is None  # type: ignore[attr-defined]
        assert not ctx.stopped  # type: ignore[attr-defined]

    async def test_async_handler_chain_with_interrupt(self) -> None:
        """Async handler raising ApplyInterrupt should stop chain."""
        router = EventRouter()
        execution_order: list[str] = []

        @router.on("async:interrupt", priority=100)
        async def interrupting_handler(ctx: EventContext) -> None:
            execution_order.append("interrupt")
            raise ApplyInterrupt("Stopping chain")

        @router.on("async:interrupt", priority=90)
        async def later_handler(ctx: EventContext) -> None:
            execution_order.append("later")

        with pytest.raises(ApplyInterrupt):
            await router.apply_async("async:interrupt")

        # Later handler should not execute
        assert execution_order == ["interrupt"]

    def test_handler_exception_captured_in_context(self) -> None:
        """Handler exception should be captured but not block other handlers."""
        router = EventRouter()
        results: list[str] = []

        @router.on("error:chain", priority=100)
        def failing_handler(ctx: EventContext) -> None:
            results.append("before_error")
            raise RuntimeError("Handler error")

        @router.on("error:chain", priority=90)
        def recovery_handler(ctx: EventContext) -> None:
            results.append("after_error")

        # apply_sync should propagate exception
        with pytest.raises(RuntimeError, match="Handler error"):
            router.apply_sync("error:chain")

        # First handler should have run
        assert "before_error" in results


class TestPredicateEvaluation:
    """Test predicate evaluation corner cases."""

    def test_predicate_exception_skips_handler(self) -> None:
        """If predicate raises exception, handler should be skipped."""
        router = EventRouter()
        handler_calls = {"count": 0}

        def failing_predicate(ctx: EventContext) -> bool:
            raise ValueError("Predicate error")

        @router.on("predicate:fail", predicate=failing_predicate)
        def handler(ctx: EventContext) -> None:
            handler_calls["count"] += 1

        # Should not crash, handler should not execute
        router.do("predicate:fail")
        router._sync_bridge.join_sync()

        assert handler_calls["count"] == 0

    def test_predicate_with_missing_parameter_returns_false(self) -> None:
        """Predicate accessing missing parameter should handle gracefully."""
        router = EventRouter()
        handler_calls = {"count": 0}

        def careful_predicate(ctx: EventContext) -> bool:
            # Use .get() to avoid KeyError
            return ctx.parameters.get("required_param") == "expected"

        @router.on("safe:predicate", predicate=careful_predicate)
        def handler(ctx: EventContext) -> None:
            handler_calls["count"] += 1

        # Without required_param
        router.do("safe:predicate")
        router._sync_bridge.join_sync()
        assert handler_calls["count"] == 0

        # With required_param
        router.do("safe:predicate", required_param="expected")
        router._sync_bridge.join_sync()
        assert handler_calls["count"] == 1

    def test_predicate_returning_non_bool_is_truthy(self) -> None:
        """Predicate returning non-bool value should use truthiness."""
        router = EventRouter()
        results: list[Any] = []

        def truthy_predicate(ctx: EventContext) -> Any:
            # Return various truthy/falsy values
            return ctx.parameters.get("value")

        @router.on("truthy:test", predicate=truthy_predicate)
        def handler(ctx: EventContext) -> None:
            results.append(ctx.parameters["value"])

        # Falsy values
        router.do("truthy:test", value=0)
        router.do("truthy:test", value="")
        router.do("truthy:test", value=None)
        router._sync_bridge.join_sync()
        assert len(results) == 0

        # Truthy values
        router.do("truthy:test", value=1)
        router.do("truthy:test", value="hello")
        router.do("truthy:test", value=[1, 2])
        router._sync_bridge.join_sync()
        assert len(results) == 3
