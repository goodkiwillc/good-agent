"""MessageList implementation with versioning support."""

from __future__ import annotations

import weakref
from collections.abc import Iterable
from typing import (
    TYPE_CHECKING,
    Any,
    Generic,
    Literal,
    SupportsIndex,
    TypeVar,
    cast,
    overload,
)

from good_agent.messages.base import Message, MessageRole
from good_agent.messages.roles import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.messages.versioning import MessageRegistry, VersionManager

T_Message = TypeVar("T_Message", bound=Message)


class MessageList(list[T_Message], Generic[T_Message]):
    """Enhanced message list with version tracking and agent integration.

    Maintains full list interface compatibility while adding versioning, agent
    integration, and message management features. Supports filtering by role
    and provides type-safe access to messages.

    Args:
        messages: Optional initial messages

    Example:
        >>> messages = MessageList[Message]()
        >>> messages.append(UserMessage("Hello"))
        >>> user_msgs = messages.filter(role="user")
    """

    def __init__(self, messages: Iterable[T_Message] | None = None):
        # Keep the list interface for backward compatibility
        super().__init__(messages or [])

        # Add versioning support (will be initialized by Agent if versioning is enabled)
        self._registry: MessageRegistry | None = None
        self._version_manager: VersionManager | None = None
        self._agent_ref: weakref.ReferenceType[Agent] | None = None

    def _set_agent(self, agent: Agent):
        self._agent_ref = weakref.ref(agent)

    def _init_versioning(
        self, registry: MessageRegistry, version_manager: VersionManager, agent: Agent
    ):
        """Initialize versioning support (called by Agent during setup).

        Args:
            registry: The message registry for storing messages
            version_manager: The version manager for tracking versions
            agent: The parent agent
        """

        self._registry = registry
        self._version_manager = version_manager
        self._agent_ref = weakref.ref(agent)

        # If we have existing messages, create initial version
        if len(self) > 0:
            message_ids = []
            for message in self:
                self._registry.register(message, agent)  # type: ignore[arg-type]
                message_ids.append(message.id)
            self._version_manager.add_version(message_ids)

    def _sync_from_version(self):
        """Sync list contents from current version (internal method)."""
        if not self._version_manager or not self._registry:
            return

        # Clear current list
        super().clear()

        # Rebuild from version
        for message_id in self._version_manager.current_version:
            message = self._registry.get(message_id)
            if message:
                super().append(cast(T_Message, message))

    @property
    def agent(self) -> Agent | None:
        """Return parent agent if available, otherwise None"""
        if self._agent_ref is not None:
            return self._agent_ref()
        return None

    def append(self, message: T_Message) -> None:
        """Append message with version tracking.

        Args:
            message: The message to append
        """
        # Standard list append
        super().append(message)

        # If versioning is enabled, update version
        if self._version_manager and self._registry and self._agent_ref:
            agent = self._agent_ref()
            if agent:
                self._registry.register(message, agent)  # type: ignore[arg-type]
                new_version = self._version_manager.current_version
                new_version.append(message.id)
                self._version_manager.add_version(new_version)

    @overload
    def __setitem__(self, index: SupportsIndex, message: T_Message) -> None: ...

    @overload
    def __setitem__(self, index: slice, message: Iterable[T_Message]) -> None: ...

    def __setitem__(self, index: SupportsIndex | slice, message: Any) -> None:
        """Set item with version tracking.

        Args:
            index: The index or slice to set
            message: The message or messages to set
        """
        # For slices, we need special handling
        if isinstance(index, slice):
            # Standard list setitem for slices
            super().__setitem__(index, message)

            # If versioning is enabled, create new version with all current IDs
            if self._version_manager and self._registry and self._agent_ref:
                agent = self._agent_ref()
                if agent:
                    # Register all new messages
                    for msg in message:
                        if isinstance(msg, Message):
                            self._registry.register(msg, agent)  # type: ignore[arg-type]

                    # Create new version with current message IDs
                    new_version = [msg.id for msg in self]
                    self._version_manager.add_version(new_version)
        else:
            # Single item replacement
            # Standard list setitem
            super().__setitem__(index, message)

            # If versioning is enabled, create new version
            if self._version_manager and self._registry and self._agent_ref:
                agent = self._agent_ref()
                if agent and isinstance(message, Message):
                    self._registry.register(message, agent)  # type: ignore[arg-type]
                    new_version = list(self._version_manager.current_version)
                    # Convert index to int
                    idx = int(index)
                    # Update the ID at the specified index
                    if 0 <= idx < len(new_version):
                        new_version[idx] = message.id
                    elif idx == len(new_version):
                        # Appending via index
                        new_version.append(message.id)
                    self._version_manager.add_version(new_version)

    def extend(self, messages: Iterable[T_Message]) -> None:
        """Extend list with multiple messages, creating a single new version.

        Args:
            messages: Messages to add
        """
        # Convert to list to avoid consuming iterator twice
        message_list = list(messages)

        # Standard list extend
        super().extend(message_list)

        # If versioning is enabled, create single new version
        if self._version_manager and self._registry and self._agent_ref:
            agent = self._agent_ref()
            if agent:
                new_version = list(self._version_manager.current_version)
                for message in message_list:
                    self._registry.register(message, agent)  # type: ignore[arg-type]
                    new_version.append(message.id)
                self._version_manager.add_version(new_version)

    def clear(self) -> None:
        """Clear all messages and create empty version."""
        super().clear()

        # If versioning is enabled, create empty version
        if self._version_manager:
            self._version_manager.add_version([])

    def prepend(self, message: T_Message) -> None:
        """Add message at the beginning with versioning support.

        Args:
            message: The message to prepend
        """
        # Insert at beginning
        super().insert(0, message)

        # If versioning is enabled, create new version
        if self._version_manager and self._registry and self._agent_ref:
            agent = self._agent_ref()
            if agent:
                # Register the message
                self._registry.register(message, agent)  # type: ignore[arg-type]

                # Create new version with message prepended
                current_ids = self._version_manager.current_version.copy()
                new_ids = [message.id] + current_ids
                self._version_manager.add_version(new_ids)

    def replace_at(self, index: int, message: T_Message) -> None:
        """Replace message at index with versioning support.

        Args:
            index: The index to replace at
            message: The message to set
        """
        # Use __setitem__ which already handles versioning
        self[index] = message

    @overload
    def filter(
        self,
        role: Literal["system"],
        **kwargs: Any,
    ) -> MessageList[SystemMessage]: ...

    @overload
    def filter(
        self,
        role: Literal["user"],
        **kwargs: Any,
    ) -> MessageList[UserMessage]: ...

    @overload
    def filter(
        self,
        role: Literal["assistant"],
        **kwargs: Any,
    ) -> MessageList[AssistantMessage]: ...

    @overload
    def filter(
        self,
        role: Literal["tool"],
        **kwargs: Any,
    ) -> MessageList[ToolMessage]: ...

    @overload
    def filter(
        self,
        role: None = None,
        **kwargs: Any,
    ) -> MessageList[T_Message]: ...

    def filter(self, role: MessageRole | None = None, **kwargs) -> MessageList:
        """Filter messages by role or other attributes."""
        result = self

        if role is not None:
            # Type-specific filtering based on role
            filtered: list[Message] = []
            for m in result:
                if m.role == role:
                    filtered.append(m)
            result = MessageList(filtered)  # type: ignore[arg-type]

        for key, value in kwargs.items():
            filtered = []
            for m in result:
                if getattr(m, key, None) == value:
                    filtered.append(m)
            result = MessageList(filtered)  # type: ignore[arg-type]

        return result

    @property
    def user(self) -> MessageList[UserMessage]:
        """Get all user messages."""
        filtered = [m for m in self if isinstance(m, UserMessage)]
        return MessageList[UserMessage](filtered)

    @property
    def assistant(self) -> MessageList[AssistantMessage]:
        """Get all assistant messages."""
        filtered = [m for m in self if isinstance(m, AssistantMessage)]
        return MessageList[AssistantMessage](filtered)

    @property
    def system(self) -> MessageList[SystemMessage]:
        """Get all system messages."""
        filtered = [m for m in self if isinstance(m, SystemMessage)]
        return MessageList[SystemMessage](filtered)

    @property
    def tool(self) -> MessageList[ToolMessage]:
        """Get all tool messages."""
        filtered = [m for m in self if isinstance(m, ToolMessage)]
        return MessageList[ToolMessage](filtered)

    @overload
    def __getitem__(self, key: SupportsIndex, /) -> T_Message: ...

    @overload
    def __getitem__(self, key: slice, /) -> list[T_Message]: ...

    def __getitem__(
        self,
        key: SupportsIndex | slice,
        /,
    ) -> T_Message | list[T_Message]:
        """Support both indexing and slicing."""
        result = list.__getitem__(self, key)
        if isinstance(key, slice):
            # Return as list, not MessageList, to match parent signature
            return result
        return result


__all__ = ["MessageList", "T_Message"]
