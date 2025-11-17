from __future__ import annotations

import asyncio
import pytest

from good_agent.agent.events import AgentEventsFacade
from good_agent.components import AgentComponent
from good_agent.core.event_router import EventContext, EventRouter, on


class DummyAgent(EventRouter):
    def __init__(self) -> None:
        super().__init__()
        self.events = AgentEventsFacade(self)


class DemoComponent(AgentComponent):
    @on("component:test", priority=150)
    def handle_event(self, ctx: EventContext) -> None:
        ctx.parameters["calls"].append(("component", ctx.parameters["value"]))


def test_component_setup_registers_handlers() -> None:
    agent = DummyAgent()
    component = DemoComponent()

    component.setup(agent)
    calls: list[tuple[str, int]] = []

    agent.do("component:test", calls=calls, value=7)

    assert calls == [("component", 7)]


def test_agent_events_facade_apply_sync_and_broadcasts() -> None:
    agent = DummyAgent()
    downstream = EventRouter()
    downstream_results: list[str] = []

    @agent.on("facade:apply")
    def root_handler(ctx: EventContext) -> str:
        return f"root:{ctx.parameters['value']}"

    @downstream.on("facade:apply")
    def downstream_handler(ctx: EventContext) -> None:
        downstream_results.append(f"down:{ctx.parameters['value']}")

    agent.events.broadcast_to(downstream)
    ctx = agent.events.apply_sync("facade:apply", value=3)

    assert ctx.output == "root:3"
    assert downstream_results == ["down:3"]


@pytest.mark.asyncio()
async def test_agent_events_facade_join_handles_background_tasks() -> None:
    agent = DummyAgent()

    @agent.on("facade:async")
    async def async_handler(ctx: EventContext) -> None:
        await asyncio.sleep(0)
        ctx.parameters["seen"].append("async")

    seen: list[str] = []
    agent.do("facade:async", seen=seen)
    await agent.events.join_async()

    assert seen == ["async"]

    # Ensure sync join is safe after async join drained tasks
    agent.events.join()
