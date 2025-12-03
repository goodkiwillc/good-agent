from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

import pytest

from good_agent.core.event_router import EventContext, EventRouter


@dataclass
class RoutingCase:
    """Test case for routing logic."""

    name: str
    event: str
    payload: dict[str, Any]
    handlers: list[dict[str, Any]]
    expected_order: list[str]
    expected_output: Any = None


def test_stop_with_output_short_circuits_apply_sync() -> None:
    router = EventRouter()
    order: list[str] = []

    @router.on("matrix:stop", priority=200)
    def stopper(ctx: EventContext) -> None:
        order.append("stopper")
        ctx.stop_with_output("done")

    @router.on("matrix:stop", priority=50)
    def trailing(_: EventContext) -> None:
        order.append("trailing")

    ctx = router.apply_sync("matrix:stop")

    assert order == ["stopper"], "lower priority handler should not execute"
    assert ctx.output == "done"
    assert ctx.should_stop is True


def test_apply_sync_runs_async_handlers() -> None:
    router = EventRouter()

    @router.on("matrix:async")
    async def async_handler(ctx: EventContext) -> str:
        await asyncio.sleep(0)
        return "async-result"

    ctx = router.apply_sync("matrix:async")

    assert ctx.output == "async-result"


@pytest.mark.asyncio()
async def test_apply_async_records_exception() -> None:
    router = EventRouter(debug=True)

    @router.on("matrix:error")
    async def failing(_: EventContext) -> None:
        raise ValueError("boom")

    ctx = await router.apply_async("matrix:error")

    assert isinstance(ctx.exception, ValueError)


def test_event_trace_logging_without_rich(caplog: pytest.LogCaptureFixture) -> None:
    router = EventRouter()
    caplog.set_level(logging.INFO)

    router.set_event_trace(True, use_rich=False)
    router.set_event_trace(False, use_rich=False)

    assert "Event tracing enabled" in caplog.text
    assert "Event tracing disabled" in caplog.text


def test_event_trace_verbose_rich(monkeypatch: pytest.MonkeyPatch) -> None:
    router = EventRouter()
    printed: list[tuple[Any, ...]] = []

    class DummyConsole:
        def print(self, *args: Any, **_: Any) -> None:
            printed.append(args)

    monkeypatch.setattr("good_agent.core.event_router.core._console", DummyConsole())

    router.set_event_trace(True, verbosity=2, use_rich=True)
    router._log_event(
        "matrix:trace",
        "apply_async",
        parameters={"value": 1, "extra": "x"},
        handler_count=2,
        duration_ms=5.0,
        result="ok",
    )

    assert printed, "Rich console should have been invoked in verbose mode"


def test_broadcast_to_and_consume_from_route_events() -> None:
    producer = EventRouter()
    consumer = EventRouter()
    values: list[int] = []

    @consumer.on("matrix:broadcast")
    def handler(ctx: EventContext) -> None:
        values.append(ctx.parameters["value"])

    consumer.consume_from(producer)
    producer.do("matrix:broadcast", value=42)

    assert values == [42]


def test_broadcast_to_returns_existing_index() -> None:
    router = EventRouter()
    other = EventRouter()

    first = router.broadcast_to(other)
    second = router.broadcast_to(other)

    assert second == first == 0


@pytest.mark.parametrize(
    "case",
    [
        RoutingCase(
            name="priority_sorting",
            event="test:priority",
            payload={},
            handlers=[
                {"id": "h1", "priority": 10},
                {"id": "h2", "priority": 100},
                {"id": "h3", "priority": 50},
            ],
            expected_order=["h2", "h3", "h1"],
        ),
        RoutingCase(
            name="predicate_filtering",
            event="test:predicate",
            payload={"value": 10},
            handlers=[
                {"id": "always", "priority": 100},
                {
                    "id": "gt_5",
                    "priority": 90,
                    "predicate": lambda ctx: ctx.parameters.get("value", 0) > 5,
                },
                {
                    "id": "gt_20",
                    "priority": 80,
                    "predicate": lambda ctx: ctx.parameters.get("value", 0) > 20,
                },
            ],
            expected_order=["always", "gt_5"],
        ),
        RoutingCase(
            name="stop_propagation",
            event="test:stop",
            payload={},
            handlers=[
                {"id": "first", "priority": 100, "action": "stop"},
                {"id": "second", "priority": 90},
            ],
            expected_order=["first"],
        ),
    ],
    ids=lambda c: c.name,
)
def test_routing_matrix(case: RoutingCase) -> None:
    """Table-driven test for core routing logic."""
    router = EventRouter()
    execution_order: list[str] = []

    # Register handlers dynamically
    for h_spec in case.handlers:
        handler_id = h_spec["id"]
        priority = h_spec.get("priority", 0)
        predicate = h_spec.get("predicate")
        action = h_spec.get("action")

        # Create a closure to capture handler_id and action
        def make_handler(hid: str, act: str | None) -> Any:
            def handler(ctx: EventContext) -> None:
                execution_order.append(hid)
                if act == "stop":
                    ctx.stop()
                elif act == "stop_with_output":
                    ctx.stop_with_output(f"{hid}-result")

            return handler

        router.on(case.event, priority=priority, predicate=predicate)(
            make_handler(handler_id, action)
        )

    # Execute
    ctx = router.apply_sync(case.event, **case.payload)

    # Verify
    assert execution_order == case.expected_order
    if case.expected_output:
        assert ctx.output == case.expected_output


def test_predicate_object_handling() -> None:
    """Test that Predicate objects work alongside callable predicates."""
    router = EventRouter()
    executed = False

    class ValuePredicate:
        def __init__(self, min_val: int):
            self.min_val = min_val

        def __call__(self, context: EventContext) -> bool:
            return context.parameters.get("val", 0) >= self.min_val

    @router.on("test:pred_obj", predicate=ValuePredicate(10))
    def handler(ctx: EventContext) -> None:
        nonlocal executed
        executed = True

    # Should not fire
    router.apply_sync("test:pred_obj", val=5)
    assert not executed

    # Should fire
    router.apply_sync("test:pred_obj", val=15)
    assert executed


def test_wildcard_event_routing() -> None:
    """Test that '*' wildcard handlers receive all events."""
    router = EventRouter()
    captured: list[str] = []

    @router.on("*")
    def wildcard(ctx: EventContext) -> None:
        captured.append(f"wildcard:{ctx.event}")

    @router.on("specific:event")
    def specific(ctx: EventContext) -> None:
        captured.append("specific")

    router.apply_sync("specific:event")
    router.apply_sync("other:event")

    # Order depends on priority, default is 0 for both.
    # Since wildcard was registered first, it might run first or second depending on stable sort.
    # EventRouter sort is stable, so insertion order matters for equal priority.
    assert "wildcard:specific:event" in captured
    assert "specific" in captured
    assert "wildcard:other:event" in captured
    assert len(captured) == 3
