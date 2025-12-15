from abc import ABC, ABCMeta, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any, Generic, TypeVar

if TYPE_CHECKING:
    from good_agent.agent import Agent

T = TypeVar("T")  # State type


class StatefulResourceMeta(ABCMeta):
    """Metaclass for StatefulResource that collects tool methods."""

    _resource_tools: dict[str, Any]

    def __new__(mcs, name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Collect tool methods from this class and its bases
        cls._resource_tools = {}

        # Walk through the MRO to collect all tool methods
        for base in reversed(cls.__mro__):
            for attr_name, attr_value in base.__dict__.items():
                # Check if this is a BoundTool descriptor
                if hasattr(attr_value, "_is_bound_tool"):
                    # This is a BoundTool descriptor created by the @tool decorator
                    cls._resource_tools[attr_name] = attr_value
                # Also check for legacy tool-decorated methods (backward compatibility)
                elif hasattr(attr_value, "_tool_metadata"):
                    # This is a legacy tool-decorated method
                    cls._resource_tools[attr_name] = attr_value
                elif hasattr(attr_value, "__class__") and attr_value.__class__.__name__ == "Tool":
                    # This is a Tool instance (shouldn't happen but handle it)
                    cls._resource_tools[attr_name] = attr_value

        return cls


class StatefulResource(ABC, Generic[T], metaclass=StatefulResourceMeta):
    """Base class for stateful resources that interact with agents.

    Minimal implementation focusing on:
    - State management
    - Tool registration lifecycle
    - Agent binding via context manager
    """

    _resource_tools: dict[str, Any]  # Populated by metaclass or get_tools

    def __init__(self, name: str):
        self.name = name
        self._state: T | None = None
        self._initialized = False

    @property
    def state(self) -> T:
        """Get current state."""
        if self._state is None:
            raise RuntimeError(f"Resource {self.name} not initialized")
        return self._state

    @state.setter
    def state(self, value: T):
        """Set state."""
        self._state = value

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the resource."""
        pass

    @abstractmethod
    async def persist(self) -> None:
        """Persist any changes."""
        pass

    def get_tools(self) -> list:
        """Return tools to register with agent.

        Returns a list of Tool instances collected by the metaclass.
        """
        from good_agent.tools.bound_tools import BoundTool
        from good_agent.tools.tools import wrap_callable_as_tool

        tools = []

        # Register each tool method
        for method_name, method in self._resource_tools.items():
            # Check if this is a BoundTool descriptor
            if isinstance(method, BoundTool):
                # Get the Tool instance bound to this resource instance
                tool_instance = getattr(self, method_name)
                tools.append(tool_instance)
            # Check if method has _tool_metadata from legacy decorator
            elif hasattr(method, "_tool_metadata"):
                # Get the bound method from this instance
                bound_method = getattr(self, method_name)
                # Wrap it as a Tool
                tool = wrap_callable_as_tool(bound_method)
                tools.append(tool)
            # Check if it's already a Tool instance
            elif hasattr(method, "__class__") and method.__class__.__name__ == "Tool":
                tools.append(method)

        return tools

    @asynccontextmanager
    async def __call__(self, agent: Agent):
        """Bind resource to agent temporarily.

        Uses agent's branch and tools context managers for clean isolation.
        """
        # Initialize if needed
        if not self._initialized:
            await self.initialize()
            self._initialized = True

        # Use branch context for message isolation
        async with agent.branch() as messages:
            # Update system message with edit context
            if messages[0] is not None and messages[0].role == "system":
                original_content = messages[0].content
                messages[0] = messages[0].copy_with(
                    content=self._create_context_prefix() + "\n\n" + original_content
                )
            else:
                messages.set_system_message(self._create_context_prefix())

            # Use tools context manager to replace tools temporarily
            tool_list = self.get_tools()

            # Handle both list and dict return types for backwards compatibility
            if isinstance(tool_list, dict):
                tool_list = list(tool_list.values())

            async with agent.tools(mode="replace", tools=tool_list):
                # Agent now has only resource-specific tools
                # Original tools will be automatically restored on exit
                yield self

    def _create_context_prefix(self) -> str:
        """Create context prefix for system message."""
        return f"""<|edit-context|>
You are now editing {self.name}.

This is a forked context specifically for editing. The original conversation context and history are preserved below.
Use the provided tools to read and modify the content.
When you're done editing, use the save tool to persist changes and return to the main context.
<|/edit-context|>"""
