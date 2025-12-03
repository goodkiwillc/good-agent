from __future__ import annotations

import asyncio

import pytest

from good_agent.core.event_router import (
    EventContext,
    EventRouter,
    LifecyclePhase,
    emit,
)


@pytest.fixture()
def router() -> EventRouter:
    return EventRouter()


def test_handlers_respect_priority_order(router: EventRouter) -> None:
    calls: list[str] = []

    @router.on("demo:event", priority=10)
    def low(_: EventContext) -> None:
        calls.append("low")

    @router.on("demo:event", priority=200)
    def high(_: EventContext) -> None:
        calls.append("high")

    router.do("demo:event")
    assert calls == ["high", "low"]


def test_predicate_controls_execution(router: EventRouter) -> None:
    calls: list[str] = []

    @router.on("demo:predicate", predicate=lambda ctx: ctx.parameters["flag"])
    def only_true(_: EventContext) -> None:
        calls.append("true")

    router.do("demo:predicate", flag=False)
    router.do("demo:predicate", flag=True)

    assert calls == ["true"]


class LifecycleComponent(EventRouter):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[str] = []

    @emit("lifecycle:work", phases=LifecyclePhase.BEFORE | LifecyclePhase.AFTER)
    async def work(self, value: int) -> str:
        await asyncio.sleep(0)
        return f"work:{value}"


@pytest.mark.asyncio()
async def test_emit_decorator_fires_lifecycle_events() -> None:
    component = LifecycleComponent()
    before: list[int] = []
    after: list[str] = []

    @component.on("lifecycle:work:before")
    def before_handler(ctx: EventContext) -> None:
        before.append(ctx.parameters["value"])

    @component.on("lifecycle:work:after")
    def after_handler(ctx: EventContext) -> None:
        after.append(ctx.parameters["result"])

    result = await component.work(value=7)

    assert result == "work:7"
    assert before == [7]
    assert after == ["work:7"]
