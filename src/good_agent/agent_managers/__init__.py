"""Agent module - refactored into focused manager classes."""

from __future__ import annotations

from .messages import MessageManager
from .state import AgentState, AgentStateMachine

# Import will happen in agent.py to avoid circular imports
# MessageManager and AgentStateMachine are used internally by Agent

__all__: list[str] = ["MessageManager", "AgentStateMachine", "AgentState"]
