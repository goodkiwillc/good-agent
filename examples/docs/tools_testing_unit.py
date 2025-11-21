"""Unit testing tools independently using pytest."""

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
    elif operation == "divide":
        if b == 0:
            raise ValueError("Division by zero not allowed")
        return a / b
    else:
        raise ValueError(f"Unknown operation: {operation}")


@pytest.mark.asyncio
async def test_calculate_tool():
    async with Agent("Test agent", tools=[calculate]) as agent:
        # Record initial message count
        initial_count = len(agent.messages)

        # Test direct invocation using agent.invoke
        result = await agent.invoke(calculate, operation="add", a=5, b=3)

        # Verify result
        assert result.success is True
        assert result.response == 8.0
        assert result.tool_name == "calculate"

        # Verify invoke() appended messages to conversation history
        # Should add: 1 assistant message (tool call) + 1 tool message (response)
        assert len(agent.messages) == initial_count + 2

        # Verify the tool call message was added
        tool_call_msg = agent.assistant[-1]
        assert tool_call_msg.role == "assistant"
        assert len(tool_call_msg.tool_calls) > 0
        assert tool_call_msg.tool_calls[0].name == "calculate"

        # Verify the tool response message was added
        tool_response_msg = agent.tool[-1]
        assert tool_response_msg.role == "tool"
        assert tool_response_msg.tool_name == "calculate"
        assert tool_response_msg.content == "8.0"


@pytest.mark.asyncio
async def test_error_handling():
    async with Agent("Test agent", tools=[calculate]) as agent:
        initial_count = len(agent.messages)

        # Test error case
        result = await agent.invoke(calculate, operation="divide", a=10, b=0)

        assert result.success is False
        assert "Division by zero" in result.error
        assert result.traceback is not None

        # Verify error was recorded in conversation history
        assert len(agent.messages) == initial_count + 2

        # Tool response should contain the error
        tool_response_msg = agent.tool[-1]
        assert "Division by zero" in tool_response_msg.content


async def main():
    """Run unit tests demonstrating tool testing patterns."""
    print("Run with: uv run pytest examples/docs/tools_testing_unit.py -v")


if __name__ == "__main__":
    asyncio.run(main())
