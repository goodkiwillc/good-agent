"""
Test backwards compatibility of the ToolManager after adding context manager support.
"""

import pytest
from good_agent import Agent, tool


@tool
async def sample_tool(value: str) -> str:
    """A test tool."""
    return f"test: {value}"


@pytest.mark.asyncio
async def test_tool_manager_dict_api_still_works():
    """Test that ToolManager still works as a dict-like object."""
    async with Agent("Test agent") as agent:
        # Test setting a tool using dict API
        agent.tools["sample_tool"] = sample_tool

        # Test __contains__
        assert "sample_tool" in agent.tools

        # Test __getitem__
        tool_obj = agent.tools["sample_tool"]
        assert tool_obj is not None

        # Test __len__
        initial_count = len(agent.tools)

        # Test __setitem__ again
        from good_agent import tool as tool_decorator

        @tool_decorator
        async def another_tool() -> str:
            return "another"

        agent.tools["another"] = another_tool
        assert len(agent.tools) == initial_count + 1

        # Test __delitem__
        del agent.tools["another"]
        assert "another" not in agent.tools
        assert len(agent.tools) == initial_count

        # Test keys()
        assert "sample_tool" in agent.tools.keys()

        # Test values()
        assert sample_tool in agent.tools.values()

        # Test items()
        items = dict(agent.tools.items())
        assert "sample_tool" in items

        # Test as_list()
        tools_list = agent.tools.as_list()
        assert len(tools_list) > 0

        # Test iteration
        tool_names = []
        for tool in agent.tools:
            tool_names.append(tool.name if hasattr(tool, "name") else str(tool))
        assert len(tool_names) > 0


@pytest.mark.asyncio
async def test_tool_manager_is_still_property():
    """Test that agent.tools is still a property returning ToolManager."""
    async with Agent("Test agent") as agent:
        # Should be accessible as property
        tools = agent.tools

        # Should be a ToolManager instance
        from good_agent.tools.tools import ToolManager

        assert isinstance(tools, ToolManager)

        # Property should return same instance
        assert agent.tools is tools


@pytest.mark.asyncio
async def test_tool_manager_context_doesnt_break_normal_usage():
    """Test that adding context manager doesn't break normal tool usage."""
    async with Agent("Test agent", tools=[sample_tool]) as agent:
        # Normal tool access should work
        assert "sample_tool" in agent.tools

        # Tool should be callable
        tool_obj = agent.tools["sample_tool"]
        result = await tool_obj(_agent=agent, value="hello")
        assert result.response == "test: hello"

        # Adding new tools should work
        from good_agent import tool as tool_decorator

        @tool_decorator
        async def dynamic_tool(x: int) -> int:
            return x * 2

        agent.tools["dynamic"] = dynamic_tool
        assert "dynamic" in agent.tools

        # Calling dynamic tool should work
        dynamic_obj = agent.tools["dynamic"]
        result = await dynamic_obj(_agent=agent, x=5)
        assert result.response == 10
