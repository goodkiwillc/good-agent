# coverage: ignore file
# Rationale: this module only re-exports Agent manager classes for import ergonomics.
"""Agent module - refactored into focused manager classes."""

from __future__ import annotations

from .components import ComponentRegistry
from .context import ContextManager
from .core import Agent, AgentConfigParameters, AgentInitialize
from .events import AgentEventsFacade
from .llm import LLMCoordinator
from .messages import MessageManager
from .modes import ModeContext, ModeManager, ModeTransition
from .state import AgentState, AgentStateMachine
from .tasks import AgentTaskManager
from .tools import ToolExecutor
from .versioning import AgentVersioningManager

__all__: list[str] = [
    "Agent",
    "AgentConfigParameters",
    "MessageManager",
    "AgentStateMachine",
    "AgentState",
    "ToolExecutor",
    "AgentTaskManager",
    "LLMCoordinator",
    "ComponentRegistry",
    "ContextManager",
    "AgentEventsFacade",
    "AgentVersioningManager",
    "AgentInitialize",
    "ModeManager",
    "ModeContext",
    "ModeTransition",
]
