from typing import Any, cast

import pytest
from good_agent import Agent, AgentComponent, tool
from good_agent.tools import BoundTool, Tool


class SampleComponent(AgentComponent):
    """Sample component with tool methods."""

    def __init__(self):
        super().__init__()
        self.state = {"counter": 0}

    @tool
    async def increment(self, amount: int = 1) -> int:
        """Increment the counter.

        Args:
            amount: Amount to increment by
        """
        self.state["counter"] += amount
        return self.state["counter"]

    @tool(name="reset_counter")  # type: ignore[arg-type]
    def reset(self) -> str:
        """Reset the counter to zero."""
        self.state["counter"] = 0
        return "Counter reset"


@pytest.mark.asyncio
async def test_tool_methods_are_bound_tool_descriptors():
    """Test that @tool decorated methods become BoundTool descriptors at class level."""
    # Access from class should return BoundTool descriptor
    class_attr = SampleComponent.__dict__.get("increment")
    assert isinstance(class_attr, BoundTool), "Expected BoundTool descriptor at class level"

    # Verify metadata is preserved
    assert class_attr.metadata.name == "increment"
    assert "Increment the counter" in class_attr.metadata.description


@pytest.mark.asyncio
async def test_tool_methods_become_tool_instances():
    """Test that accessing tool methods from instances returns Tool instances."""
    component = SampleComponent()

    # Access from instance should return Tool instance
    tool_instance: Tool[Any, Any] = cast(Tool[Any, Any], component.increment)
    assert isinstance(tool_instance, Tool), "Expected Tool instance at instance level"

    # Verify Tool properties
    assert tool_instance.name == "increment"
    assert "Increment the counter" in tool_instance.description

    # Test the reset tool with custom name
    reset_tool: Tool[Any, Any] = cast(Tool[Any, Any], component.reset)
    assert isinstance(reset_tool, Tool)
    assert reset_tool.name == "reset_counter"  # Custom name


@pytest.mark.asyncio
async def test_bound_tools_maintain_component_state():
    """Test that Tool instances maintain access to component state."""
    component = SampleComponent()
    tool_instance: Tool[Any, Any] = cast(Tool[Any, Any], component.increment)

    # Call the tool directly
    result = await tool_instance(amount=5)
    assert result.success
    assert result.response == 5

    # Verify it modified component state
    assert component.state["counter"] == 5

    # Call again to verify state persistence
    result = await tool_instance(amount=3)
    assert result.response == 8
    assert component.state["counter"] == 8


@pytest.mark.asyncio
async def test_tool_instances_are_cached_per_component():
    """Test that Tool instances are cached and reused for the same component instance."""
    component = SampleComponent()

    # Access the tool multiple times
    tool1: Tool[Any, Any] = cast(Tool[Any, Any], component.increment)
    tool2: Tool[Any, Any] = cast(Tool[Any, Any], component.increment)

    # Should be the same instance (cached)
    assert tool1 is tool2


@pytest.mark.asyncio
async def test_different_components_have_separate_tools():
    """Test that different component instances have separate Tool instances."""
    component1 = SampleComponent()
    component2 = SampleComponent()

    tool1: Tool[Any, Any] = cast(Tool[Any, Any], component1.increment)
    tool2: Tool[Any, Any] = cast(Tool[Any, Any], component2.increment)

    # Should be different instances
    assert tool1 is not tool2

    # Modify state through one tool
    await tool1(amount=10)
    assert component1.state["counter"] == 10
    assert component2.state["counter"] == 0  # Should not affect other component


@pytest.mark.asyncio
async def test_bound_tools_work_with_agent():
    """Test that bound Tool instances work correctly when registered with an Agent."""
    component = SampleComponent()
    agent = Agent("Test agent", extensions=[component])
    await agent.initialize()

    # Wait for component tool registration to complete
    if hasattr(component, "_tool_registration_task") and component._tool_registration_task:
        await component._tool_registration_task

    # Tools should be registered
    assert "increment" in agent.tools
    assert "reset_counter" in agent.tools

    # Get tool from agent
    agent_tool = agent.tools["increment"]
    assert isinstance(agent_tool, Tool)

    # Should be the same instance as accessed from component
    assert agent_tool is cast(Tool[Any, Any], component.increment)

    # Test calling through agent
    result = await agent.invoke("increment", amount=7)
    assert result.success
    assert result.response == 7
    assert component.state["counter"] == 7

    # Reset through agent
    result = await agent.invoke("reset_counter")
    assert result.success
    assert result.response == "Counter reset"
    assert component.state["counter"] == 0

    await agent.events.close()


@pytest.mark.asyncio
async def test_bound_tool_attribute_protection():
    """Test that BoundTool descriptors prevent attribute assignment."""
    component = SampleComponent()

    # Should not be able to set the tool attribute
    with pytest.raises(AttributeError, match="Cannot set tool attribute"):
        component.increment = "something else"
