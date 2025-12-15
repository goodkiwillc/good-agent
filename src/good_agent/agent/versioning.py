"""Versioning Manager - Manages message versioning and version history."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ulid import ULID

from good_agent.core.ulid_monotonic import create_monotonic_ulid
from good_agent.events import AgentEvents
from good_agent.messages.versioning import VersionManager

if TYPE_CHECKING:
    from good_agent.agent import Agent

logger = logging.getLogger(__name__)


class AgentVersioningManager:
    """Manages agent versioning operations.

    This manager handles all version-related operations including:
    - Version ID management (changes with modifications)
    - Version history tracking
    - Reverting to previous versions
    - Version change events
    """

    def __init__(self, agent: Agent) -> None:
        """Initialize versioning manager.

        Args:
            agent: Parent Agent instance
        """
        self.agent = agent

        # Version ID (changes with each modification)
        self._version_id: ULID = create_monotonic_ulid()

        # Version history (legacy - kept for backward compatibility)
        self._versions: list[list[ULID]] = []

        # Low-level version manager
        self._version_manager = VersionManager()

    @property
    def version_id(self) -> ULID:
        """Agent's version identifier (changes with modifications)."""
        return self._version_id

    @property
    def current_version(self) -> list[ULID]:
        """Get the current version's message IDs.

        Returns:
            List of message IDs in the current version
        """
        return self._version_manager.current_version

    @property
    def version_manager(self) -> VersionManager:
        """Get the underlying version manager.

        Returns:
            The VersionManager instance
        """
        return self._version_manager

    def revert_to_version(self, version_index: int) -> None:
        """Revert the agent's messages to a specific version.

        This is non-destructive - it creates a new version with the content
        of the target version rather than deleting newer versions.

        Args:
            version_index: The version index to revert to
        """
        # Revert the version manager
        self._version_manager.revert_to(version_index)

        # Sync the message list with the new version
        self.agent._messages._sync_from_version()

        # Update version ID to indicate change
        self._version_id = create_monotonic_ulid()

        logger.debug(f"Agent {self.agent._id} reverted to version {version_index}")

    def update_version(self) -> None:
        """Update the agent's version ID when state changes."""
        old_version = self._version_id
        # Use monotonic ULID generation to ensure strict ordering
        # create_monotonic_ulid() ensures monotonic ordering even within the same millisecond
        # by incrementing the random component when timestamps are identical
        self._version_id = create_monotonic_ulid()

        # Update version history
        current_message_ids = [msg.id for msg in self.agent._messages]
        self._versions.append(current_message_ids)

        # Emit agent:version:change event
        changes = {
            "messages": len(self.agent._messages),
            "last_version_messages": len(self._versions[-2]) if len(self._versions) > 1 else 0,
        }
        # @TODO: event naming
        self.agent.do(
            AgentEvents.AGENT_VERSION_CHANGE,
            agent=self.agent,
            old_version=old_version,
            new_version=self._version_id,
            changes=changes,
        )
