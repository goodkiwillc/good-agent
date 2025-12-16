import types

import pytest

from good_agent import Agent, AgentEvents, tool


@pytest.mark.asyncio
async def test_execute_iteration_after_fires_per_iteration_and_after_tools():
    @tool
    async def echo(value: str) -> str:
        return f"echo:{value}"

    async with Agent("System", tools=[echo]) as agent:
        iterations_after: list[tuple[int, int | None]] = []

        @agent.on(AgentEvents.EXECUTE_ITERATION_AFTER)
        def capture_after(ctx):
            iterations_after.append(
                (ctx.parameters["iteration"], ctx.parameters.get("messages_count"))
            )

        with agent.mock(
            agent.mock.create(
                "",
                role="assistant",
                tool_calls=[{"name": "echo", "arguments": {"value": "ping"}}],
            ),
            agent.mock.create("done", role="assistant"),
        ):
            async for _ in agent.execute("hi", max_iterations=5):
                pass

        assert [iteration for iteration, _ in iterations_after] == [0, 1]
        # After first iteration we should have user + assistant + tool messages recorded
        assert iterations_after[0][1] and iterations_after[0][1] >= 4


@pytest.mark.asyncio
async def test_execute_error_allows_recovery_messages():
    agent = Agent("System")
    await agent.initialize()

    @agent.on(AgentEvents.EXECUTE_ERROR)
    async def recover(ctx):
        ctx.output = [agent.model.create_message("recovered", role="assistant")]

    async def failing_call(*_args, **_kwargs):
        raise RuntimeError("boom")

    agent._llm_call = types.MethodType(failing_call, agent)

    responses: list[str] = []
    async for message in agent.execute("hello"):
        responses.append(str(message.content))

    assert responses == ["recovered"]
    assert agent.messages[-1].content == "recovered"

    await agent.close(reason="cleanup")


@pytest.mark.asyncio
async def test_agent_close_events_fire():
    agent = Agent("System")
    await agent.initialize()

    events: list[tuple[str, str | None]] = []

    @agent.on(AgentEvents.AGENT_CLOSE_BEFORE)
    async def before(ctx):
        events.append(("before", ctx.parameters.get("reason")))

    @agent.on(AgentEvents.AGENT_CLOSE_AFTER)
    async def after(ctx):
        events.append(("after", ctx.parameters.get("reason")))

    await agent.close(reason="cleanup")

    assert events == [("before", "cleanup"), ("after", "cleanup")]
