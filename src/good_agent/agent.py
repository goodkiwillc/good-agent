"""Backward compatibility module - imports from refactored agent package.

This module provides backward compatibility for code that imports directly from
`good_agent.agent`. All functionality has been moved to the `good_agent.agent`
package with the main Agent class in `good_agent.agent.core`.

For new code, import directly from good_agent:
    from good_agent import Agent

Or from the agent.core module:
    from good_agent.agent.core import Agent
"""

from __future__ import annotations

# Import from specific modules to avoid circular imports
from .agent.components import ComponentRegistry
from .agent.context import ContextManager
from .agent.core import Agent
from .agent.llm import LLMCoordinator
from .agent.messages import MessageManager
from .agent.state import AgentState, AgentStateMachine
from .agent.tools import ToolExecutor
from .agent.versioning import AgentVersioningManager

__all__ = [
    "Agent",
    "AgentState",
    "AgentStateMachine",
    "ComponentRegistry",
    "ContextManager",
    "LLMCoordinator",
    "MessageManager",
    "ToolExecutor",
    "AgentVersioningManager",
]
