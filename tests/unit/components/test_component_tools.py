from typing import TYPE_CHECKING, Any, TypeVar, cast
from collections.abc import Callable

import pytest
from good_agent import Agent, AgentComponent, tool
from good_agent.tools import BoundTool, Tool
from pydantic import BaseModel

FuncT = TypeVar("FuncT", bound=Callable[..., Any])


def component_tool(**kwargs: Any) -> Callable[[FuncT], FuncT]:
    """Helper decorator to preserve typing when using tool kwargs."""

    def decorator(func: FuncT) -> FuncT:
        decorated = tool(**kwargs)(func)
        return cast(FuncT, decorated)

    return decorator


class ToDoItem(BaseModel):
    """A single to-do item."""

    task: str
    completed: bool = False


class ToDoList(BaseModel):
    """A to-do list."""

    name: str | None = None
    items: list[ToDoItem]


class TaskManager(AgentComponent):
    """Example component with tool methods."""

    lists: dict[str, ToDoList] = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.lists = {}

    @tool
    def create_list(self, name: str | None = None) -> str:
        """Create a new to-do list with an optional name. Returns the ID of the new list."""
        list_id = f"list-{len(self.lists) + 1}"
        self.lists[list_id] = ToDoList(name=name, items=[])
        return list_id

    @tool
    def add_task(self, list_id: str, task: str) -> bool:
        """Add a task to the specified list."""
        if list_id in self.lists:
            self.lists[list_id].items.append(ToDoItem(task=task))
            return True
        return False

    @tool
    async def get_list(self, list_id: str) -> ToDoList | None:
        """Get a to-do list by ID."""
        return self.lists.get(list_id)

    # Regular method (not a tool)
    def get_all_lists(self) -> dict[str, ToDoList]:
        """Get all to-do lists."""
        return self.lists


@pytest.mark.asyncio
async def test_component_tools_registration():
    """Test that component tools are properly registered with the agent."""
    # Create agent with TaskManager component
    task_manager = TaskManager()
    async with Agent(
        "You are a task management assistant", extensions=[task_manager]
    ) as agent:
        # Tools should now be registered immediately after initialize() completes

        # Check that tools were registered
        assert "create_list" in agent.tools
        assert "add_task" in agent.tools
        assert "get_list" in agent.tools

        # Regular methods should not be registered
        assert "get_all_lists" not in agent.tools

        # Tools should be callable
        create_tool = agent.tools["create_list"]
        assert isinstance(create_tool, Tool)

        # Test calling the tool
        result = await create_tool(_agent=agent, name="Shopping")
        assert result.success
        assert result.response == "list-1"
        assert task_manager.lists["list-1"].name == "Shopping"


@pytest.mark.asyncio
async def test_component_tools_execution():
    """Test that component tools can be executed through the agent."""
    task_manager = TaskManager()
    async with Agent(
        "You are a task management assistant. Use the tools to manage tasks.",
        extensions=[task_manager],
    ) as agent:
        # Call agent with a request that should use tools
        await agent.call("Create a new list called 'Work Tasks'")

        # Check that a list was created
        assert len(task_manager.lists) > 0

        # The list should have the requested name
        created_lists = [
            lst for lst in task_manager.lists.values() if lst.name == "Work Tasks"
        ]
        assert len(created_lists) > 0


@pytest.mark.asyncio
async def test_component_tool_with_agent_reference():
    """Test that tool methods have access to the agent via self.agent."""
    from good_agent import tool  # Import tool locally to avoid scope issues

    class SmartTaskManager(AgentComponent):
        @tool
        def create_contextual_list(self, name: str) -> str:
            """Create a list with context from the agent."""
            # Access agent through self.agent
            f"list-{id(self)}"
            # In real usage, you could use agent context, messages, etc.
            return f"Created {name} for agent with {len(self.agent.messages)} messages"

    manager = SmartTaskManager()
    async with Agent("Assistant", extensions=[manager]) as agent:
        # Add some messages
        agent.append("Hello")
        agent.append("Create a list")

        # Call the tool
        _tool = agent.tools["create_contextual_list"]
        result = await _tool(_agent=agent, name="Test")
        assert result.success
        assert "3 messages" in result.response  # System + 2 user messages


@pytest.mark.asyncio
async def test_component_tool_type_checking():
    """Test that type checking works correctly with component tools."""
    # This test mainly verifies that the code compiles with proper type hints

    class TypedManager(AgentComponent):
        @tool
        def sync_method(self, x: int) -> int:
            """A synchronous tool method."""
            return x * 2

        @tool
        async def async_method(self, x: int) -> int:
            """An async tool method."""
            return x * 3

    manager = TypedManager()
    async with Agent("Test", extensions=[manager]) as agent:
        # Both sync and async methods should be registered as tools
        assert "sync_method" in agent.tools
        assert "async_method" in agent.tools

        # Both should work when called
        sync_result = await agent.tools["sync_method"](_agent=agent, x=5)
        assert sync_result.response == 10

        async_result = await agent.tools["async_method"](_agent=agent, x=5)
        assert async_result.response == 15

        # Type checking verification (this would be caught at type-check time)
        if TYPE_CHECKING:
            # The decorated methods should preserve their signatures
            sync_descriptor = manager.__class__.__dict__["sync_method"]
            async_descriptor = manager.__class__.__dict__["async_method"]
            cast(BoundTool[AgentComponent, Any, Any], sync_descriptor)
            cast(BoundTool[AgentComponent, Any, Any], async_descriptor)


@pytest.mark.asyncio
async def test_component_tool_with_hide_parameter():
    """Test that component tools can hide parameters from the schema."""

    class SecureManager(AgentComponent):
        @component_tool(hide=["api_key"])
        def secure_operation(self, data: str, api_key: str = "secret") -> str:
            """Perform a secure operation."""
            return f"Processed {data} with key {api_key[:3]}..."

    manager = SecureManager()
    async with Agent("Test", extensions=[manager]) as agent:
        secure_tool = agent.tools["secure_operation"]

        # The hidden parameter should not be in the tool signature
        signature = secure_tool.signature
        properties = signature["function"]["parameters"]["properties"]
        assert "data" in properties
        assert "api_key" not in properties

        # But the tool should still work with the hidden parameter
        result = await secure_tool(_agent=agent, data="test", api_key="my_secret_key")
        assert result.success
        assert "my_" in result.response
