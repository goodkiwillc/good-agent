"""Mocking tools for testing using pytest."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from good_agent import Agent


@pytest.mark.asyncio
async def test_with_mocked_tool():
    # Create mock tool
    mock_search = AsyncMock(return_value="Mocked search results")

    async with Agent("Test agent", tools=[mock_search]) as agent:
        result = await agent.invoke(mock_search, query="test")

        assert result.success is True
        assert result.response == "Mocked search results"
        mock_search.assert_called_once_with(query="test")


async def main():
    """Run mocking tests demonstrating tool mocking patterns."""
    print("Run with: uv run pytest examples/docs/tools_testing_mocking.py -v")


if __name__ == "__main__":
    asyncio.run(main())
