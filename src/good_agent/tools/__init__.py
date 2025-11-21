# Import all public API from each module to maintain backward compatibility
from good_agent.tools.agent_tool import AgentAsTool
from good_agent.tools.bound_tools import BoundTool, create_component_tool_decorator
from good_agent.tools.registry import (
    ToolRegistration,
    ToolRegistry,
    clear_tool_registry,
    get_tool_registry,
    get_tool_registry_sync,
    register_tool,
)
from good_agent.tools.tools import (
    Tool,
    ToolCall,
    ToolCallFunction,
    ToolContext,
    ToolManager,
    ToolMetadata,
    ToolParameter,
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
    "ToolParameter",
    "ToolResponse",
    "ToolSignature",
    "tool",
    "ToolCall",
    "ToolCallFunction",
    "ToolContext",
    "wrap_callable_as_tool",
    # From agent_tool.py
    "AgentAsTool",
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
