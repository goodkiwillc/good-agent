"""Unit testing custom tools."""

import asyncio

import pytest
from good_agent import Agent, tool
from pydantic import Field


@tool
async def calculate(x: int, y: int) -> int:
    """Simple calculation tool for testing."""
    return x + y


@tool
async def validated(value: int = Field(ge=0, le=100)) -> int:
    """Tool with parameter validation."""
    return value


@pytest.mark.asyncio
async def test_calculate_tool():
    """Test the calculate tool."""
    # Create agent with tool
    async with Agent("Test agent", tools=[calculate]) as agent:
        # Execute tool directly
        result = await agent.tools["calculate"](_agent=agent, x=5, y=3)

        assert result.success
        assert result.response == 8


@pytest.mark.asyncio
async def test_tool_with_validation():
    """Test tool parameter validation."""
    async with Agent("Test agent", tools=[validated]) as agent:
        # Valid input
        result = await agent.tools["validated"](_agent=agent, value=50)
        assert result.success

        # Invalid input should fail validation
        with pytest.raises(Exception):
            await agent.tools["validated"](_agent=agent, value=150)


async def main():
    """Run unit tests demonstrating tool testing patterns."""
    print("Run with: uv run pytest examples/docs/custom_tools_testing.py -v")


if __name__ == "__main__":
    asyncio.run(main())
