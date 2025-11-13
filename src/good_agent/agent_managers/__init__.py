"""Agent module - refactored into focused manager classes."""

from __future__ import annotations

from .components import ComponentRegistry
from .context import ContextManager
from .llm import LLMCoordinator
from .messages import MessageManager
from .state import AgentState, AgentStateMachine
from .tools import ToolExecutor
from .versioning import AgentVersioningManager

# Import will happen in agent.py to avoid circular imports
# MessageManager, AgentStateMachine, ToolExecutor, LLMCoordinator, and ComponentRegistry are used internally by Agent

__all__: list[str] = [
    "MessageManager",
    "AgentStateMachine",
    "AgentState",
    "ToolExecutor",
    "LLMCoordinator",
    "ComponentRegistry",
    "ContextManager",
    "AgentVersioningManager",
]
