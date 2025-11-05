# Import all public API from each module to maintain backward compatibility
from .bound_tools import BoundTool, create_component_tool_decorator
from .registry import (
    ToolRegistration,
    ToolRegistry,
    clear_tool_registry,
    get_tool_registry,
    get_tool_registry_sync,
    register_tool,
)
from .tools import (
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolContext,
    ToolManager,
    ToolMetadata,
    ToolResponse,
    ToolSignature,
    tool,
    wrap_callable_as_tool,
)

__all__ = [
    # From tools.py
    "Tool",
    "ToolManager",
    "ToolMetadata",
    "ToolResponse",
    "ToolSignature",
    "tool",
    "ToolCall",
    "ToolCallFunction",
    "ToolContext",
    "wrap_callable_as_tool",
    # From registry.py
    "ToolRegistry",
    "ToolRegistration",
    "get_tool_registry",
    "get_tool_registry_sync",
    "register_tool",
    "clear_tool_registry",
    # From bound_tools.py
    "BoundTool",
    "create_component_tool_decorator",
]
