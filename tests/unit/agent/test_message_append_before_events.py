import pytest

from good_agent import Agent
from good_agent.events import (
    AgentEvents,
    ExecuteBeforeParams,
    MessageAppendBeforeParams,
)
from good_agent.messages import Message
from good_agent.tools import ToolCall, ToolCallFunction


@pytest.mark.asyncio
async def test_message_append_before_replacement():
    async with Agent("System") as agent:
        called = False

        @agent.on(AgentEvents.MESSAGE_APPEND_BEFORE)
        async def replace(ctx):
            nonlocal called
            called = True
            original = ctx.parameters["message"]
            return original.model_copy(update={"content_parts": ["modified"]})

        message = agent.model.create_message("original")
        ctx = await agent.events.typed(MessageAppendBeforeParams, Message).apply(
            AgentEvents.MESSAGE_APPEND_BEFORE,
            message=message,
            agent=agent,
            output=message,
        )

        assert called
        assert ctx.exception is None
        assert ctx.return_value and ctx.return_value.content == "modified"

        agent.append("original")

        assert called
        assert agent.messages[-1].content == "modified"


@pytest.mark.asyncio
async def test_message_append_before_passthrough():
    async with Agent("System") as agent:
        observed = False

        @agent.on(AgentEvents.MESSAGE_APPEND_BEFORE)
        def observe(_ctx):
            nonlocal observed
            observed = True

        agent.append("unchanged")

        assert observed
        assert agent.messages[-1].content == "unchanged"


@pytest.mark.asyncio
async def test_execute_before_interceptable(monkeypatch):
    async with Agent("System") as agent:
        called = False

        @agent.on(AgentEvents.EXECUTE_BEFORE)
        def override_iterations(ctx):
            nonlocal called
            called = True
            ctx.output = 2

        ctx = await agent.apply_typed(
            AgentEvents.EXECUTE_BEFORE,
            ExecuteBeforeParams,
            int,
            agent=agent,
            max_iterations=1,
            output=1,
        )

        assert ctx.return_value == 2

        async def fake_llm_call(**_kwargs):
            msg = agent.model.create_message(
                "response",
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="call-1",
                        function=ToolCallFunction(name="dummy", arguments="{}"),
                    )
                ],
            )
            await agent._append_message(msg)
            return msg

        monkeypatch.setattr(agent, "_llm_call", fake_llm_call)
        monkeypatch.setattr(agent._tool_executor, "get_pending_tool_calls", lambda: [])

        async def fake_resolve_pending_tool_calls():
            if False:
                yield None

        monkeypatch.setattr(agent._tool_executor, "resolve_pending_tool_calls", fake_resolve_pending_tool_calls)

        outputs = []
        async for message in agent.execute("prompt", max_iterations=1):
            outputs.append(message)

        assert called
        assert len(outputs) == 2
        assert all(m.role == "assistant" for m in outputs)
