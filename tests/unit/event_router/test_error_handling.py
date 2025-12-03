from __future__ import annotations

import pytest
from good_agent.core.event_router import ApplyInterrupt, EventContext, EventRouter


@pytest.fixture()
def router() -> EventRouter:
    return EventRouter(debug=True)


@pytest.mark.asyncio()
async def test_apply_interrupt_stops_handler_chain(router: EventRouter) -> None:
    order: list[str] = []

    @router.on("demo:error", priority=200)
    def interrupter(ctx: EventContext) -> None:
        order.append("first")
        raise ApplyInterrupt()

    @router.on("demo:error", priority=50)
    def should_not_run(_: EventContext) -> None:
        order.append("second")

    ctx = await router.apply_async("demo:error")

    assert order == ["first"]
    assert ctx.exception is None


@pytest.mark.asyncio()
async def test_handler_exception_is_captured(router: EventRouter) -> None:
    order: list[str] = []

    @router.on("demo:exception", priority=150)
    def failing(_: EventContext) -> None:
        raise ValueError("boom")

    @router.on("demo:exception", priority=50)
    def still_runs(_: EventContext) -> None:
        order.append("ran")

    ctx = await router.apply_async("demo:exception")

    assert order == ["ran"]
    assert isinstance(ctx.exception, ValueError)


def test_predicate_failure_is_ignored(router: EventRouter) -> None:
    calls: list[str] = []

    def bad_predicate(_: EventContext) -> bool:
        raise RuntimeError("bad predicate")

    @router.on("demo:predicate:error", predicate=bad_predicate)
    def should_skip(_: EventContext) -> None:
        calls.append("skip")

    router.do("demo:predicate:error")

    assert calls == []
