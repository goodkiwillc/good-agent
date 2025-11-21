"""Integration testing tools within agent context using pytest."""

import asyncio

import pytest

from good_agent import Agent, tool


@tool
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic math operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unknown operation: {operation}")


@pytest.mark.asyncio
async def test_tool_in_agent():
    async with Agent("Test agent", tools=[calculate]) as agent:
        # Test agent can use tool
        response = await agent.call("Calculate 7 times 8")

        # Verify tool was called
        tool_messages = [msg for msg in agent.tool if msg.tool_name == "calculate"]
        assert len(tool_messages) >= 1

        # Verify response contains result
        assert "56" in response.content


async def main():
    """Run integration tests demonstrating tool usage within agent context."""
    print("Run with: uv run pytest examples/docs/tools_testing_integration.py -v")


if __name__ == "__main__":
    asyncio.run(main())
