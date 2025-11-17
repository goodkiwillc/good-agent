from __future__ import annotations

import asyncio
import logging
from typing import Any

import pytest

from good_agent.core.event_router import EventContext, EventRouter


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
