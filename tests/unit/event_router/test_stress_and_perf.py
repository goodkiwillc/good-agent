from __future__ import annotations

import asyncio

import pytest

from good_agent.core.event_router import EventContext, EventRouter


@pytest.mark.slow()
def test_fire_and_forget_under_load_cleans_up_tasks() -> None:
    router = EventRouter()

    @router.on("stress:async")
    async def handler(_: EventContext) -> None:
        await asyncio.sleep(0)

    for _ in range(200):
        router.do("stress:async")

    router.join()

    assert router._sync_bridge.task_count == 0
