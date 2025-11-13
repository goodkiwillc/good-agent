"""Context Manager - Manages fork, thread, and context operations."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from good_agent.config_types import AGENT_CONFIG_KEYS
from good_agent.events import AgentEvents
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.thread_context import ForkContext, ThreadContext

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages fork, thread, and context operations.

    This manager handles all agent context operations including:
    - Forking agents with configuration cloning
    - Fork context creation for isolated operations
    - Thread context creation for temporary modifications
    """

    def __init__(self, agent: "Agent") -> None:
        """Initialize context manager.

        Args:
            agent: Parent Agent instance
        """
        self.agent = agent

    def fork(
        self,
        include_messages: bool = True,
        **kwargs: Any,
    ) -> "Agent":
        """
        Fork the agent into a new agent with the same configuration (or modified).

        Creates a new agent with:
        - New session_id (different from parent)
        - Same version_id (until modified)
        - Optionally copied messages (with new IDs)
        - Same or modified configuration

        Args:
            include_messages: Whether to copy messages to the forked agent
            **kwargs: Configuration overrides for the new agent
        """
        # Avoid circular import
        from good_agent.agent import Agent

        # Get current config and update with kwargs
        config = self.agent.config.as_dict()
        config.update(kwargs)

        # Filter config to only include valid AgentConfigParameters
        valid_params = AGENT_CONFIG_KEYS
        filtered_config = {k: v for k, v in config.items() if k in valid_params}

        override_keys = {
            key
            for key in kwargs
            if key
            in {
                "language_model",
                "mock",
                "tool_manager",
                "template_manager",
                "extensions",
            }
        }
        self.agent._component_registry.clone_extensions_for_config(
            filtered_config, override_keys
        )

        # Create new agent using the constructor
        new_agent = Agent(**filtered_config)

        # Copy messages if requested
        if include_messages:
            for msg in self.agent._messages:
                # Create new message with same content but new ID
                # We need to create a new instance to get a new ID
                msg_data = msg.model_dump(exclude={"id", "role"})

                # Preserve content_parts directly to avoid triggering render
                # which would cause event loop conflicts in async contexts
                if hasattr(msg, "content_parts"):
                    msg_data["content_parts"] = msg.content_parts

                # Create new message of the same type and add via proper methods
                match msg:
                    case SystemMessage():
                        # Use set_system_message for system messages
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="system"
                        )
                        new_agent.set_system_message(new_msg)
                    case UserMessage():
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="user"
                        )
                        new_agent.append(new_msg)
                    case AssistantMessage():
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="assistant"
                        )
                        new_agent.append(new_msg)
                    case ToolMessage():
                        new_msg = new_agent.model.create_message(
                            **msg_data, role="tool"
                        )
                        new_agent.append(new_msg)
                    case _:
                        raise ValueError(f"Unknown message type: {type(msg).__name__}")

        # Set version to match source (until modified)
        new_agent._version_id = self.agent._version_id

        # Initialize version history with current state
        if new_agent._messages:
            new_agent._versions = [[msg.id for msg in new_agent._messages]]

        # Emit agent:fork event
        # @TODO: event naming
        self.agent.do(
            AgentEvents.AGENT_FORK_AFTER,
            parent=self.agent,
            child=new_agent,
            config_changes=kwargs,
        )

        return new_agent

    def fork_context(
        self, truncate_at: int | None = None, **fork_kwargs
    ) -> "ForkContext":
        """Create a fork context for isolated operations.

        Args:
            truncate_at: Optional index to truncate messages at
            **fork_kwargs: Additional arguments to pass to fork()

        Returns:
            ForkContext instance to use with async with

        Example:
            async with agent.fork_context(truncate_at=5) as forked:
                response = await forked.call("Summarize")
                # Response only exists in fork
        """
        from good_agent.thread_context import ForkContext

        return ForkContext(self.agent, truncate_at, **fork_kwargs)

    def thread_context(self, truncate_at: int | None = None) -> "ThreadContext":
        """Create a thread context for temporary modifications.

        Args:
            truncate_at: Optional index to truncate messages at

        Returns:
            ThreadContext instance to use with async with

        Example:
            async with agent.thread_context(truncate_at=5) as ctx_agent:
                response = await ctx_agent.call("Summarize")
                # After context, agent has original messages + response
        """
        from good_agent.thread_context import ThreadContext

        return ThreadContext(self.agent, truncate_at)
