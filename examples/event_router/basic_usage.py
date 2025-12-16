"""Minimal EventRouter example covering registration and async dispatch."""

from __future__ import annotations

import asyncio

from good_agent.core.event_router import EventContext, EventRouter

router = EventRouter()


@router.on("demo:greet", priority=200)
async def greet(ctx: EventContext[dict, str]) -> None:
    name = ctx.parameters["name"]
    ctx.output = f"Hello, {name}!"


@router.on("demo:greet", priority=50)
def audit(ctx: EventContext[dict, str]) -> None:
    print(f"greet called for {ctx.parameters['name']}")


async def main() -> None:
    ctx = await router.apply_async("demo:greet", name="Ada")
    print(ctx.output)


if __name__ == "__main__":
    asyncio.run(main())
