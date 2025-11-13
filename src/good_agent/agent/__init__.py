"""Agent module - refactored into focused manager classes."""

from __future__ import annotations

from .components import ComponentRegistry
from .context import ContextManager
from .core import Agent, AgentInitialize
from .llm import LLMCoordinator
from .messages import MessageManager
from .state import AgentState, AgentStateMachine
from .tools import ToolExecutor
from .versioning import AgentVersioningManager

__all__: list[str] = [
    "Agent",
    "MessageManager",
    "AgentStateMachine",
    "AgentState",
    "ToolExecutor",
    "LLMCoordinator",
    "ComponentRegistry",
    "ContextManager",
    "AgentVersioningManager",
    "AgentInitialize",
]
