from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ulid import ULID

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from good_agent.agent.core import Agent


class ForkContext:
    """Context manager that creates a temporary forked agent.

    Creates a complete fork of the agent that can be used for isolated operations.
    The forked agent is discarded when the context exits.
    """

    def __init__(self, agent: Agent, truncate_at: int | None = None, **fork_kwargs):
        """Initialize fork context.

        Args:
            agent: The agent to fork
            truncate_at: Optional index to truncate messages at
            **fork_kwargs: Additional arguments to pass to agent.fork()
        """
        self.agent = agent
        self.truncate_at = truncate_at
        self.fork_kwargs = fork_kwargs
        self.forked_agent: Agent | None = None

    async def __aenter__(self) -> Agent:
        """Create and return forked agent."""
        # Fork the agent with messages
        self.forked_agent = self.agent._context_manager.fork(
            include_messages=True, **self.fork_kwargs
        )

        # Wait for forked agent to be ready
        await self.forked_agent.initialize()

        if self.truncate_at is not None:
            # Truncate the forked agent's messages if requested
            # We need to create a new version with only the first N messages
            if hasattr(self.forked_agent, "_version_manager"):
                # Get current message IDs
                current_ids = self.forked_agent._version_manager.current_version
                # Truncate to requested length
                truncated_ids = current_ids[: self.truncate_at]
                # Create new version with truncated list
                self.forked_agent._version_manager.add_version(truncated_ids)
                # Sync messages
                self.forked_agent._messages._sync_from_version()
            else:
                # Fallback for non-versioned agents
                from good_agent.messages import MessageList

                truncated = list(self.forked_agent.messages[: self.truncate_at])
                self.forked_agent._messages = MessageList(truncated)
                self.forked_agent._messages._set_agent(self.forked_agent)

        logger.debug(f"Created fork of agent {self.agent._id} -> {self.forked_agent._id}")
        return self.forked_agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up forked agent."""
        if self.forked_agent:
            # Close the forked agent
            await self.forked_agent.events.close()
            logger.debug(f"Closed forked agent {self.forked_agent._id}")
        self.forked_agent = None


class ThreadContext:
    """Context manager for temporary thread modifications with restoration.

    Allows temporary modifications to the thread (truncation, replacements)
    while preserving any new messages added during the context.
    """

    def __init__(self, agent: Agent, truncate_at: int | None = None):
        """Initialize thread context.

        Args:
            agent: The agent whose thread to modify
            truncate_at: Optional index to truncate messages at
        """
        self.agent = agent
        self.truncate_at = truncate_at
        self._original_version_ids: list[ULID] = []
        self._entry_version_count: int = 0
        self._entry_message_count: int = 0

    async def __aenter__(self) -> Agent:
        """Enter context with modified view."""
        # Ensure agent is ready
        await self.agent.initialize()

        if hasattr(self.agent, "_version_manager"):
            # Versioned agent path
            # Save the current version ID list
            self._original_version_ids = self.agent._version_manager.current_version.copy()
            self._entry_version_count = len(self._original_version_ids)

            if self.truncate_at is not None:
                # Create a temporary version showing only first N messages
                truncated_ids = self._original_version_ids[: self.truncate_at]
                self.agent._version_manager.add_version(truncated_ids)
                self.agent._messages._sync_from_version()

                logger.debug(f"Truncated agent {self.agent._id} to {self.truncate_at} messages")
        else:
            # Non-versioned agent path (for backward compatibility)
            self._entry_message_count = len(self.agent.messages)

            if self.truncate_at is not None:
                # Store original messages
                self._original_messages = list(self.agent.messages)
                # Truncate directly (less safe but works without versioning)
                from good_agent.messages import MessageList

                truncated = list(self.agent.messages[: self.truncate_at])
                self.agent._messages = MessageList(truncated)
                self.agent._messages._set_agent(self.agent)

        return self.agent

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Restore original thread but keep new messages."""
        if hasattr(self.agent, "_version_manager"):
            # Versioned agent path
            if self.truncate_at is not None:
                # Get current version after any operations in context
                current_version_ids = self.agent._version_manager.current_version

                # Extract IDs of messages added during context
                # These are any messages beyond the truncation point
                new_message_ids = current_version_ids[self.truncate_at :]

                # Restore: original version + any new messages
                restored_ids = self._original_version_ids + new_message_ids

                # Create the restored version
                self.agent._version_manager.add_version(restored_ids)
                self.agent._messages._sync_from_version()

                logger.debug(
                    f"Restored agent {self.agent._id} with {len(new_message_ids)} new messages"
                )
            else:
                # No truncation - but we still need to handle replacements
                # Check if any messages were replaced (different IDs at same positions)
                current_version_ids = self.agent._version_manager.current_version

                # Find truly new messages (added beyond original length)
                new_message_ids = current_version_ids[len(self._original_version_ids) :]

                # Restore original messages + new additions
                restored_ids = self._original_version_ids + new_message_ids

                # Create the restored version
                self.agent._version_manager.add_version(restored_ids)
                self.agent._messages._sync_from_version()

                if new_message_ids:
                    logger.debug(
                        f"Restored agent {self.agent._id} with {len(new_message_ids)} new messages"
                    )
        else:
            # Non-versioned agent path
            if self.truncate_at is not None and hasattr(self, "_original_messages"):
                # Get any new messages added
                current_messages = list(self.agent.messages)
                new_messages = current_messages[self.truncate_at :]

                # Restore original + new
                from good_agent.messages import MessageList

                restored = self._original_messages + new_messages
                self.agent._messages = MessageList(restored)
                self.agent._messages._set_agent(self.agent)


def fork_context(agent: Agent, truncate_at: int | None = None, **fork_kwargs) -> ForkContext:
    """Create a fork context for isolated operations.

    Args:
        agent: The agent to fork
        truncate_at: Optional index to truncate messages at
        **fork_kwargs: Additional arguments to pass to agent.fork()

    Returns:
        ForkContext instance to use with async with

    Example:
        async with fork_context(agent, truncate_at=5) as forked:
            response = await forked.call("Summarize")
            # Response only exists in fork
    """
    return ForkContext(agent, truncate_at, **fork_kwargs)


def thread_context(agent: Agent, truncate_at: int | None = None) -> ThreadContext:
    """Create a thread context for temporary modifications.

    Args:
        agent: The agent whose thread to modify
        truncate_at: Optional index to truncate messages at

    Returns:
        ThreadContext instance to use with async with

    Example:
        async with thread_context(agent, truncate_at=5) as ctx_agent:
            response = await ctx_agent.call("Summarize")
            # After context, agent has original messages + response
    """
    return ThreadContext(agent, truncate_at)
