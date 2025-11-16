from __future__ import annotations

from good_agent.core.event_router import EventContext, EventRouter


def test_handler_added_during_dispatch_runs_next_time() -> None:
    router = EventRouter()
    calls: list[str] = []

    @router.on("race:dynamic", priority=100)
    def first(_: EventContext) -> None:
        calls.append("first")

        @router.on("race:dynamic", priority=10)
        def later(_: EventContext) -> None:
            calls.append("later")

    router.do("race:dynamic")
    assert calls == ["first"]

    router.do("race:dynamic")
    assert calls == ["first", "first", "later"]


def test_nested_event_emissions_do_not_deadlock() -> None:
    router = EventRouter()
    order: list[str] = []

    @router.on("race:outer")
    def outer(_: EventContext) -> None:
        order.append("outer")
        router.do("race:inner")

    @router.on("race:inner")
    def inner(_: EventContext) -> None:
        order.append("inner")

    router.do("race:outer")
    router.join()

    assert order == ["outer", "inner"]
