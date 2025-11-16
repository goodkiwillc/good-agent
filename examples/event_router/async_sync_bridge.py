"""Demonstrate calling async handlers from synchronous code via EventRouter."""

from __future__ import annotations

import asyncio
import time

from good_agent.core.event_router import EventContext, EventRouter


router = EventRouter()


@router.on("demo:compute")
async def compute(ctx: EventContext[dict, float]) -> float:
    await asyncio.sleep(0.01)
    value = ctx.parameters["value"]
    return value * 2


def main() -> None:
    start = time.perf_counter()
    ctx = router.apply_sync("demo:compute", value=21)
    duration_ms = (time.perf_counter() - start) * 1000
    print(f"Result={ctx.output}, took={duration_ms:.2f}ms")


if __name__ == "__main__":
    main()
