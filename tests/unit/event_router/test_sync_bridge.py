from __future__ import annotations

import asyncio

from good_agent.core.event_router import EventContext, EventRouter


def test_apply_sync_runs_async_handlers() -> None:
    router = EventRouter()

    @router.on("bridge:test")
    async def handler(ctx: EventContext) -> str:
        await asyncio.sleep(0)
        ctx.output = "async-complete"
        return ctx.output

    ctx = router.apply_sync("bridge:test")
    assert ctx.output == "async-complete"


def test_event_context_available_inside_async_handler() -> None:
    router = EventRouter()

    @router.on("bridge:ctx")
    async def handler(ctx: EventContext) -> None:
        # EventRouter.ctx should resolve to the same context even when called via sync bridge
        assert router.ctx is ctx

    router.apply_sync("bridge:ctx")


def test_do_with_async_handler_finishes_after_join() -> None:
    router = EventRouter()
    calls: list[str] = []

    @router.on("bridge:do")
    async def handler(_: EventContext) -> None:
        await asyncio.sleep(0)
        calls.append("done")

    router.do("bridge:do")
    router.join()

    assert calls == ["done"]
