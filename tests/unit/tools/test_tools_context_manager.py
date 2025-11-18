import pytest
from typing import Any, cast

from good_agent import Agent, Tool, tool
from good_agent.tools import BoundTool


ToolLike = Tool[Any, Any] | BoundTool[Any, Any, Any]


def as_tool(tool_obj: ToolLike) -> Tool[Any, Any]:
    assert isinstance(tool_obj, Tool)
    return cast(Tool[Any, Any], tool_obj)


# Define test tools for use in tests
@tool
async def original_tool(value: str) -> str:
    """An original tool."""
    return f"original: {value}"


original_tool = as_tool(original_tool)


@tool
async def replacement_tool(value: str) -> str:
    """A replacement tool."""
    return f"replacement: {value}"


replacement_tool = as_tool(replacement_tool)


@tool
async def additional_tool(value: str) -> str:
    """An additional tool."""
    return f"additional: {value}"


additional_tool = as_tool(additional_tool)


@tool
async def another_original_tool(value: str) -> str:
    """Another original tool."""
    return f"another: {value}"


another_original_tool = as_tool(another_original_tool)


class TestToolsContextManager:
    """Test suite for agent.tools() context manager."""

    @pytest.mark.asyncio
    async def test_tools_context_manager_exists(self):
        """Test that agent.tools() method exists and is callable."""
        async with Agent("Test agent") as agent:
            # Check that tools() method exists
            assert hasattr(agent, "tools")

            # Check that we can call it as a context manager
            # This will fail initially as the method doesn't exist yet
            assert callable(getattr(agent, "tools", None))

    @pytest.mark.asyncio
    async def test_replace_mode_replaces_all_tools(self):
        """Test that replace mode replaces all tools within context."""
        async with Agent(
            "Test agent", tools=[original_tool, another_original_tool]
        ) as agent:
            # Verify original tools
            assert "original_tool" in agent.tools
            assert "another_original_tool" in agent.tools
            assert "replacement_tool" not in agent.tools

            # Use replace mode
            async with agent.tools(mode="replace", tools=[replacement_tool]):
                # Inside context: only replacement tool should exist
                assert "replacement_tool" in agent.tools
                assert "original_tool" not in agent.tools
                assert "another_original_tool" not in agent.tools
                assert len(agent.tools) == 1

            # After context: original tools restored
            assert "original_tool" in agent.tools
            assert "another_original_tool" in agent.tools
            assert "replacement_tool" not in agent.tools
            assert len(agent.tools) == 2

    @pytest.mark.asyncio
    async def test_append_mode_adds_tools(self):
        """Test that append mode adds new tools without removing existing ones."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            # Verify original state
            assert "original_tool" in agent.tools
            assert "additional_tool" not in agent.tools
            original_count = len(agent.tools)

            # Use append mode
            async with agent.tools(mode="append", tools=[additional_tool]):
                # Inside context: both tools should exist
                assert "original_tool" in agent.tools
                assert "additional_tool" in agent.tools
                assert len(agent.tools) == original_count + 1

            # After context: only original tools remain
            assert "original_tool" in agent.tools
            assert "additional_tool" not in agent.tools
            assert len(agent.tools) == original_count

    @pytest.mark.asyncio
    async def test_filter_mode_filters_tools(self):
        """Test that filter mode selectively includes tools based on filter function."""
        async with Agent(
            "Test agent", tools=[original_tool, another_original_tool, additional_tool]
        ) as agent:
            # Verify all tools present
            assert len(agent.tools) == 3

            # Use filter mode to keep only tools with "original" in name
            async with agent.tools(
                mode="filter", filter_fn=lambda name, tool: "original" in name
            ):
                # Inside context: only "original" tools
                assert "original_tool" in agent.tools
                assert "another_original_tool" in agent.tools
                assert "additional_tool" not in agent.tools
                assert len(agent.tools) == 2

            # After context: all tools restored
            assert "original_tool" in agent.tools
            assert "another_original_tool" in agent.tools
            assert "additional_tool" in agent.tools
            assert len(agent.tools) == 3

    @pytest.mark.asyncio
    async def test_nested_contexts_work_correctly(self):
        """Test that nested tool contexts work correctly."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            # Original state
            assert "original_tool" in agent.tools
            assert len(agent.tools) == 1

            # First context: append a tool
            async with agent.tools(mode="append", tools=[additional_tool]):
                assert len(agent.tools) == 2
                assert "additional_tool" in agent.tools

                # Nested context: replace all tools
                async with agent.tools(mode="replace", tools=[replacement_tool]):
                    # Only replacement tool
                    assert len(agent.tools) == 1
                    assert "replacement_tool" in agent.tools
                    assert "original_tool" not in agent.tools
                    assert "additional_tool" not in agent.tools

                # Back to first context: original + additional
                assert len(agent.tools) == 2
                assert "original_tool" in agent.tools
                assert "additional_tool" in agent.tools
                assert "replacement_tool" not in agent.tools

            # Back to original state
            assert len(agent.tools) == 1
            assert "original_tool" in agent.tools
            assert "additional_tool" not in agent.tools

    @pytest.mark.asyncio
    async def test_empty_replace_clears_all_tools(self):
        """Test that replace mode with no tools clears all tools."""
        async with Agent(
            "Test agent", tools=[original_tool, another_original_tool]
        ) as agent:
            assert len(agent.tools) == 2

            # Replace with empty list
            async with agent.tools(mode="replace", tools=[]):
                # No tools available
                assert len(agent.tools) == 0

            # Original tools restored
            assert len(agent.tools) == 2

    @pytest.mark.asyncio
    async def test_default_mode_is_replace(self):
        """Test that default mode is 'replace' when not specified."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            # Use context manager without specifying mode
            async with agent.tools(tools=[replacement_tool]):
                # Should replace by default
                assert "replacement_tool" in agent.tools
                assert "original_tool" not in agent.tools

            # Original restored
            assert "original_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_tools_remain_callable_in_context(self):
        """Test that tools remain callable within the context."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            # Test original tool works
            orig_tool = agent.tools["original_tool"]
            result = await orig_tool(_agent=agent, value="test")
            assert result.response == "original: test"

            # Replace with new tool
            async with agent.tools(mode="replace", tools=[replacement_tool]):
                # Test replacement tool works
                repl_tool = agent.tools["replacement_tool"]
                result = await repl_tool(_agent=agent, value="test")
                assert result.response == "replacement: test"

            # Original tool works again
            orig_tool = agent.tools["original_tool"]
            result = await orig_tool(_agent=agent, value="test")
            assert result.response == "original: test"

    @pytest.mark.asyncio
    async def test_exception_in_context_restores_tools(self):
        """Test that tools are restored even if exception occurs in context."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            original_tools = dict(agent.tools)

            # Context that raises exception
            with pytest.raises(ValueError):
                async with agent.tools(mode="replace", tools=[replacement_tool]):
                    # Verify replacement worked
                    assert "replacement_tool" in agent.tools
                    # Raise exception
                    raise ValueError("Test exception")

            # Tools should be restored despite exception
            assert dict(agent.tools) == original_tools
            assert "original_tool" in agent.tools
            assert "replacement_tool" not in agent.tools

    @pytest.mark.asyncio
    async def test_tools_context_with_tool_manager_dict_api(self):
        """Test that tools context manager preserves ToolManager dict-like API."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            # Test dict-like operations work
            async with agent.tools(mode="append", tools=[additional_tool]):
                # Test __contains__
                assert "additional_tool" in agent.tools

                # Test __getitem__
                tool = agent.tools["additional_tool"]
                assert tool is not None

                # Test keys()
                assert "additional_tool" in agent.tools.keys()

                # Test values()
                assert additional_tool in agent.tools.values()

                # Test items()
                items = dict(agent.tools.items())
                assert "additional_tool" in items

                # Test __len__
                assert len(agent.tools) == 2

    @pytest.mark.asyncio
    async def test_filter_mode_with_none_filter_keeps_all(self):
        """Test that filter mode with None filter function keeps all tools."""
        async with Agent(
            "Test agent", tools=[original_tool, another_original_tool]
        ) as agent:
            original_count = len(agent.tools)

            # Filter with None should keep everything
            async with agent.tools(mode="filter", filter_fn=None):
                assert len(agent.tools) == original_count
                assert "original_tool" in agent.tools
                assert "another_original_tool" in agent.tools

    @pytest.mark.asyncio
    async def test_append_mode_with_duplicate_names_overwrites(self):
        """Test that append mode overwrites tools with same name."""

        # Create a modified version of original_tool
        async def modified_original_impl(value: str) -> str:
            """Modified version of original tool."""
            return f"modified: {value}"

        modified_original = as_tool(
            tool(name="original_tool")(cast(Any, modified_original_impl))
        )

        async with Agent("Test agent", tools=[original_tool]) as agent:
            # Test original behavior
            result = await agent.tools["original_tool"](_agent=agent, value="test")
            assert result.response == "original: test"

            # Append tool with same name
            async with agent.tools(mode="append", tools=[modified_original]):
                # Should use the modified version
                result = await agent.tools["original_tool"](_agent=agent, value="test")
                assert result.response == "modified: test"

            # Original restored
            result = await agent.tools["original_tool"](_agent=agent, value="test")
            assert result.response == "original: test"

    @pytest.mark.asyncio
    async def test_context_manager_yields_tool_manager(self):
        """Test that the context manager yields the tool manager."""
        async with Agent("Test agent", tools=[original_tool]) as agent:
            async with agent.tools(mode="append", tools=[additional_tool]) as tools:
                # Should yield the tool manager
                assert tools is agent.tools
                assert "additional_tool" in tools
