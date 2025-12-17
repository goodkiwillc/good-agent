import asyncio
import threading

import pytest

from good_agent import Agent, tool
from good_agent.messages import AssistantMessage


@pytest.mark.asyncio
async def test_execute_overlaps_serialize_mutations(monkeypatch):
    async with Agent() as agent:
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        original_append = agent._message_manager._append_message

        async def blocking_append(message):
            async with agent.state_guard():
                if getattr(message, "content", None) == "first":
                    first_started.set()
                    await release_first.wait()
                return await original_append(message)

        monkeypatch.setattr(agent._message_manager, "_append_message", blocking_append)

        async def collect(content: str):
            messages = []
            async for msg in agent.execute(content):
                messages.append(msg)
            return messages

        task_one = asyncio.create_task(collect("first"))
        await asyncio.wait_for(first_started.wait(), timeout=5)

        task_two = asyncio.create_task(collect("second"))
        await asyncio.sleep(0)

        assert not any(getattr(msg, "content", None) == "second" for msg in agent.messages)

        release_first.set()
        await asyncio.gather(task_one, task_two)

        contents = [getattr(msg, "content", None) for msg in agent.messages]
        assert contents.index("first") < contents.index("second")


@pytest.mark.asyncio
async def test_parallel_tool_emissions_are_ordered():
    @tool
    async def slow_tool(delay: float = 0.05):
        await asyncio.sleep(delay)
        return "slow"

    @tool
    async def fast_tool(delay: float = 0.0):
        await asyncio.sleep(delay)
        return "fast"

    async with Agent() as agent:
        await agent._tool_executor.invoke_many(
            [
                (slow_tool, {"delay": 0.05}),
                (fast_tool, {"delay": 0.0}),
            ]
        )

        assistant_message = agent.assistant[-1]
        assert isinstance(assistant_message, AssistantMessage)
        tool_calls = assistant_message.tool_calls or []

        tool_messages = list(agent.tool)
        assert [msg.tool_call_id for msg in tool_messages] == [tc.id for tc in tool_calls]
        assert [msg.tool_name for msg in tool_messages] == [tc.function.name for tc in tool_calls]


@pytest.mark.asyncio
async def test_threadsafe_proxy_executes_on_agent_loop():
    async with Agent() as agent:
        holder: dict[str, AssistantMessage] = {}

        def run_call():
            holder["assistant"] = agent.threadsafe.call("from thread")

        thread = threading.Thread(target=run_call)
        thread.start()
        thread.join(timeout=5)

        assert thread.is_alive() is False

        user_contents = [msg.content for msg in agent.user]
        assert "from thread" in user_contents
        assert isinstance(holder.get("assistant"), AssistantMessage)
