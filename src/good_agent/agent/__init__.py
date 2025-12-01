# coverage: ignore file
# Rationale: this module only re-exports Agent manager classes for import ergonomics.
"""Agent module - refactored into focused manager classes."""

from __future__ import annotations

from good_agent.agent.components import ComponentRegistry
from good_agent.agent.context import ContextManager
from good_agent.agent.core import Agent, AgentConfigParameters, AgentInitialize
from good_agent.agent.llm import LLMCoordinator
from good_agent.agent.messages import MessageManager
from good_agent.agent.modes import (
    IsolationLevel,
    ModeAccessor,
    ModeContext,
    ModeExitBehavior,
    ModeHandlerError,
    ModeManager,
    ModeTransition,
    StandaloneMode,
    mode,
)
from good_agent.agent.state import AgentState, AgentStateMachine
from good_agent.agent.system_prompt import SystemPromptManager
from good_agent.agent.tasks import AgentTaskManager
from good_agent.agent.tools import ToolExecutor
from good_agent.agent.versioning import AgentVersioningManager

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
    "AgentVersioningManager",
    "AgentInitialize",
    "IsolationLevel",
    "ModeAccessor",
    "ModeManager",
    "ModeContext",
    "ModeExitBehavior",
    "ModeHandlerError",
    "ModeTransition",
    "StandaloneMode",
    "SystemPromptManager",
    "mode",
]
