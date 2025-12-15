from __future__ import annotations

import logging
import weakref
from typing import TYPE_CHECKING, Any

from ulid import ULID

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from good_agent.agent.core import Agent
    from good_agent.messages import Message
    from good_agent.messages.store import MessageStore


class MessageNotFoundError(Exception):
    """Raised when a message cannot be found in the registry."""

    pass


class InMemoryMessageStore:
    """Simple in-memory message store for testing and development."""

    def __init__(self):
        self._messages: dict[ULID, Message] = {}

    def put(self, message: Message) -> None:
        """Store a message."""
        self._messages[message.id] = message

    def get(self, message_id: ULID) -> Message:
        """Retrieve a message by ID."""
        if message_id not in self._messages:
            raise MessageNotFoundError(f"Message {message_id} not found")
        return self._messages[message_id]

    def exists(self, message_id: ULID) -> bool:
        """Check if a message exists."""
        return message_id in self._messages


class MessageRegistry:
    """Global registry for message versions and agent ownership.

    This works alongside the existing MessageStore for persistence,
    adding version tracking and agent reference management.
    """

    def __init__(self, store: MessageStore | None = None):
        """Initialize with optional backing store for persistence."""
        self._store = store or InMemoryMessageStore()
        self._agent_refs: dict[ULID, weakref.ReferenceType[Agent]] = {}
        self._message_versions: dict[
            ULID, list[int]
        ] = {}  # Track which versions contain each message

    def register(self, message: Message, agent: Agent) -> None:
        """Register message with agent reference and persist.

        Args:
            message: The message to register
            agent: The agent that owns this message
        """
        # Store in backing store for persistence
        self._store.put(message)

        # Track agent ownership with weak reference
        self._agent_refs[message.id] = weakref.ref(agent)

        logger.debug(f"Registered message {message.id} with agent {agent._id}")

    def get(self, message_id: ULID) -> Message | None:
        """Retrieve message from store.

        Args:
            message_id: The ID of the message to retrieve

        Returns:
            The message if found, None otherwise
        """
        try:
            return self._store.get(message_id)
        except (MessageNotFoundError, AttributeError):
            return None

    def get_agent(self, message_id: ULID) -> Agent | None:
        """Get the agent that owns this message.

        Args:
            message_id: The ID of the message

        Returns:
            The agent that owns this message, or None if not found or agent was garbage collected
        """
        ref = self._agent_refs.get(message_id)
        return ref() if ref else None

    def track_version(self, message_id: ULID, version_index: int) -> None:
        """Track which versions contain this message.

        Args:
            message_id: The ID of the message
            version_index: The version index that contains this message
        """
        if message_id not in self._message_versions:
            self._message_versions[message_id] = []
        if version_index not in self._message_versions[message_id]:
            self._message_versions[message_id].append(version_index)

    def get_versions_containing(self, message_id: ULID) -> list[int]:
        """Get all version indices that contain a specific message.

        Args:
            message_id: The ID of the message

        Returns:
            List of version indices containing the message
        """
        return self._message_versions.get(message_id, [])

    def cleanup_dead_references(self) -> int:
        """Remove references to garbage collected agents.

        Returns:
            Number of references cleaned up
        """
        dead_refs = []
        for msg_id, ref in self._agent_refs.items():
            if ref() is None:
                dead_refs.append(msg_id)

        for msg_id in dead_refs:
            del self._agent_refs[msg_id]

        if dead_refs:
            logger.debug(f"Cleaned up {len(dead_refs)} dead agent references")

        return len(dead_refs)


class VersionManager:
    """Manages message version history for an agent.

    Each version is a snapshot of the message IDs at a particular point in time.
    Operations like append, replace, or revert create new versions.
    """

    def __init__(self):
        """Initialize an empty version manager."""
        self._versions: list[list[ULID]] = []
        self._current_version_index: int = -1
        self._metadata: dict[int, dict[str, Any]] = {}  # Optional metadata per version

    @property
    def current_version(self) -> list[ULID]:
        """Get current version's message IDs.

        Returns:
            List of message IDs in the current version (copy to prevent modification)
        """
        if not self._versions or self._current_version_index < 0:
            return []
        return self._versions[self._current_version_index].copy()

    @property
    def current_version_index(self) -> int:
        """Get the index of the current version.

        Returns:
            The current version index, or -1 if no versions exist
        """
        return self._current_version_index

    @property
    def version_count(self) -> int:
        """Get the total number of versions.

        Returns:
            The number of versions stored
        """
        return len(self._versions)

    def add_version(self, message_ids: list[ULID], metadata: dict[str, Any] | None = None) -> int:
        """Create a new version.

        Args:
            message_ids: List of message IDs for this version
            metadata: Optional metadata to associate with this version

        Returns:
            The index of the newly created version
        """
        # Make a copy to prevent external modification
        new_version = message_ids.copy()
        self._versions.append(new_version)
        self._current_version_index = len(self._versions) - 1

        if metadata:
            self._metadata[self._current_version_index] = metadata

        logger.debug(
            f"Created version {self._current_version_index} with {len(new_version)} messages"
        )
        return self._current_version_index

    def get_version(self, version_index: int) -> list[ULID]:
        """Get a specific version's message IDs.

        Args:
            version_index: The index of the version to retrieve

        Returns:
            List of message IDs for the specified version

        Raises:
            IndexError: If the version index is out of bounds
        """
        if version_index < 0:
            version_index = len(self._versions) + version_index

        if version_index < 0 or version_index >= len(self._versions):
            raise IndexError(
                f"Version {version_index} does not exist (have {len(self._versions)} versions)"
            )

        return self._versions[version_index].copy()

    def revert_to(self, version_index: int) -> list[ULID]:
        """Revert to a specific version by creating a new version with that content.

        This is non-destructive - it creates a new version identical to the target version
        rather than deleting newer versions.

        Args:
            version_index: The version to revert to

        Returns:
            The message IDs of the reverted version

        Raises:
            IndexError: If the version index is out of bounds
        """
        version = self.get_version(version_index)
        self.add_version(
            version,
            metadata={
                "reverted_from": self._current_version_index,
                "reverted_to": version_index,
            },
        )
        return version

    def fork_at(self, version_index: int = -1) -> VersionManager:
        """Create a fork at specific version.

        Args:
            version_index: The version to fork from (default: current version)

        Returns:
            A new VersionManager containing versions up to and including the fork point
        """
        fork = VersionManager()

        # Handle negative indices
        if version_index < 0:
            target_index = len(self._versions) + version_index
        else:
            target_index = version_index

        # Copy versions up to and including the target
        for i in range(min(target_index + 1, len(self._versions))):
            fork._versions.append(self._versions[i].copy())
            if i in self._metadata:
                fork._metadata[i] = self._metadata[i].copy()

        # Set the current version to the last copied version
        if fork._versions:
            fork._current_version_index = len(fork._versions) - 1

        logger.debug(f"Forked at version {target_index}, fork has {len(fork._versions)} versions")
        return fork

    def get_changes_between(self, version_a: int, version_b: int) -> dict[str, list[ULID]]:
        """Get the differences between two versions.

        Args:
            version_a: First version index
            version_b: Second version index

        Returns:
            Dictionary with 'added' and 'removed' message IDs
        """
        ids_a = set(self.get_version(version_a))
        ids_b = set(self.get_version(version_b))

        return {
            "added": list(ids_b - ids_a),
            "removed": list(ids_a - ids_b),
        }

    def truncate_after(self, version_index: int) -> None:
        """Remove all versions after the specified index.

        This is a destructive operation that permanently removes versions.

        Args:
            version_index: The last version to keep
        """
        if version_index < 0:
            version_index = len(self._versions) + version_index

        if version_index < len(self._versions) - 1:
            removed_count = len(self._versions) - version_index - 1
            self._versions = self._versions[: version_index + 1]
            self._current_version_index = min(self._current_version_index, version_index)

            # Clean up metadata for removed versions
            keys_to_remove = [k for k in self._metadata if k > version_index]
            for k in keys_to_remove:
                del self._metadata[k]

            logger.debug(f"Truncated {removed_count} versions after index {version_index}")

    def get_metadata(self, version_index: int) -> dict[str, Any]:
        """Get metadata for a specific version.

        Args:
            version_index: The version index

        Returns:
            Metadata dictionary for the version (empty dict if no metadata)
        """
        return self._metadata.get(version_index, {})
