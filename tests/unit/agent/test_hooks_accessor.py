from __future__ import annotations

from typing import Any

import pytest

from good_agent import Agent
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents
from good_agent.events.types import (
    ExecuteIterationParams,
    MessageAppendBeforeParams,
    ToolCallBeforeParams,
)


@pytest.mark.asyncio
async def test_hooks_registers_message_append_before() -> None:
    async with Agent("System") as agent:
        @agent.hooks.on_message_append_before
        def replace(ctx: EventContext[MessageAppendBeforeParams, Any]):
            message = ctx.parameters["message"]
            return message.model_copy(update={"content_parts": ["hooked"]})

        await agent.append_async("original", role="user")

        assert agent.messages[-1].content == "hooked"


@pytest.mark.asyncio
async def test_hooks_tool_call_before_decorator_syntax() -> None:
    async with Agent("System") as agent:
        seen: list[str | None] = []

        @agent.hooks.on_tool_call_before
        def handle(ctx: EventContext[ToolCallBeforeParams, dict[str, Any] | None]):
            seen.append(ctx.parameters.get("tool_name"))
            return {"patched": True}

        ctx = await agent.apply_typed(
            AgentEvents.TOOL_CALL_BEFORE,
            ToolCallBeforeParams,
            dict[str, Any],
            tool_name="demo",
            parameters={"value": 1},
            agent=agent,
        )

        assert seen == ["demo"]
        assert ctx.return_value == {"patched": True}


@pytest.mark.asyncio
async def test_hooks_tool_call_before_function_syntax() -> None:
    async with Agent("System") as agent:
        seen: list[str | None] = []

        def handler(ctx: EventContext[ToolCallBeforeParams, dict[str, Any] | None]):
            seen.append(ctx.parameters.get("tool_name"))
            return {"from": "function"}

        agent.hooks.on_tool_call_before(handler, priority=150)

        ctx = await agent.apply_typed(
            AgentEvents.TOOL_CALL_BEFORE,
            ToolCallBeforeParams,
            dict[str, Any],
            tool_name="demo",
            parameters={"value": 2},
            agent=agent,
        )

        assert seen == ["demo"]
        assert ctx.return_value == {"from": "function"}


@pytest.mark.asyncio
async def test_hooks_respects_priority_and_predicate() -> None:
    async with Agent("System") as agent:
        order: list[str] = []

        def first(
            ctx: EventContext[ExecuteIterationParams, dict[str, Any] | None]
        ) -> dict[str, Any]:
            order.append("high")
            return {"from": "high"}

        agent.hooks.on_execute_iteration_before(first, priority=200)

        def second(ctx: EventContext[ExecuteIterationParams, dict[str, Any] | None]) -> None:
            order.append("low")

        agent.hooks.on_execute_iteration_before(second, priority=50)

        def should_skip(
            _ctx: EventContext[ExecuteIterationParams, dict[str, Any] | None]
        ) -> bool:
            return False

        def skipped(_ctx: EventContext[ExecuteIterationParams, dict[str, Any] | None]) -> None:
            order.append("skip")

        agent.hooks.on_execute_iteration_before(skipped, predicate=should_skip)

        ctx = await agent.apply_typed(
            AgentEvents.EXECUTE_ITERATION_BEFORE,
            ExecuteIterationParams,
            dict[str, Any],
            agent=agent,
            iteration=0,
            messages_count=0,
        )

        assert order == ["high", "low"]
        assert ctx.return_value == {"from": "high"}
