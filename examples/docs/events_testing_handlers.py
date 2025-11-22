"""Test that events are emitted and handled correctly."""

import asyncio
from unittest.mock import Mock

import pytest

from good_agent import Agent, tool
from good_agent.events import AgentEvents


@tool
def test_tool(value: int) -> int:
    """Double the input value."""
    return value * 2


@pytest.mark.asyncio
async def test_message_event_handling():
    """Test message append event handling."""
    async with Agent("Test agent") as agent:
        # Set up mock handler
        handler = Mock()
        agent.on(AgentEvents.MESSAGE_APPEND_AFTER)(handler)

        # Trigger event
        agent.append("Test message")

        # Verify handler was called
        handler.assert_called_once()
        call_args = handler.call_args[0][0]  # EventContext
        assert call_args.parameters["message"].content == "Test message"


@pytest.mark.asyncio
async def test_tool_event_modification():
    """Test modifying tool arguments via events."""
    async with Agent("Test agent", tools=[test_tool]) as agent:
        # Handler that modifies arguments
        @agent.on(AgentEvents.TOOL_CALL_BEFORE)
        def modify_args(ctx):
            args = ctx.parameters["arguments"]
            if "value" in args:
                modified = args.copy()
                modified["value"] = 10  # Force value to 10
                ctx.output = modified
                return modified

        # Invoke tool with different value
        result = await agent.invoke(test_tool, value=5)

        # Should use modified value (10 * 2 = 20)
        assert result.response == 20


async def main():
    """Run the tests."""
    await test_message_event_handling()
    await test_tool_event_modification()
    print("All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
