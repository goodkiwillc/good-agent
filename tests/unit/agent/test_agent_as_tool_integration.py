import pytest

from good_agent.agent.core import Agent


@pytest.mark.asyncio
async def test_agent_as_tool_method():
    """Test that Agent.as_tool() returns a correctly configured Tool."""
    agent = Agent("Test Agent", name="test_agent")

    # Default usage
    tool = agent.as_tool()
    assert tool.name == "test_agent"
    assert "Delegate task to test_agent" in tool.description

    # Custom config
    custom_tool = agent.as_tool(
        name="custom_tool", description="Custom description", multi_turn=False
    )
    assert custom_tool.name == "custom_tool"
    assert custom_tool.description == "Custom description"
    # We can't easily check multi_turn directly on the tool instance since it wraps the method
    # but we verified AgentAsTool behavior in other tests.
    # This test mainly ensures the plumbing works.


@pytest.mark.asyncio
async def test_agent_passed_in_tools_list():
    """Test that passing an Agent in tools list works (smoke test)."""
    sub_agent = Agent("Sub Agent", name="sub_agent")
    parent_agent = Agent("Parent Agent", tools=[sub_agent])

    # Wait for tools to be registered (async init)
    await parent_agent.initialize()

    # Since tools registration might be scheduled on the loop, we need to yield to let it run
    import asyncio

    await asyncio.sleep(0.1)

    assert "sub_agent" in parent_agent.tools
    tool = parent_agent.tools["sub_agent"]
    # Verify it's a tool wrapping the agent
    assert tool.name == "sub_agent"
