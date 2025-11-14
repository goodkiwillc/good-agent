"""FilteredMessageList for role-specific message access."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Generic, TypeVar

from .base import Message, MessageContent
from .message_list import MessageList

if TYPE_CHECKING:
    from ..agent import Agent

T_Message = TypeVar("T_Message", bound=Message)


class FilteredMessageList(MessageList[T_Message], Generic[T_Message]):
    """Filtered view of messages by role with simplified append semantics.

    Provides role-specific message lists (agent.user, agent.assistant, etc.)
    with convenient append methods that automatically set the role.

    Args:
        agent: Parent agent
        role: Message role to filter by
        messages: Optional initial messages (usually from filtering)

    Example:
        >>> agent.user.append("Hello")  # Creates UserMessage automatically
        >>> agent.assistant.append("Hi!")  # Creates AssistantMessage automatically
    """

    def __init__(
        self, agent: Agent, role: str, messages: Iterable[T_Message] | None = None
    ):
        # Initialize with provided messages
        super().__init__(messages)
        self._agent = agent
        self._role = role

    def append(self, *content_parts: MessageContent, **kwargs) -> None:
        """Append message with automatic role assignment.

        Args:
            *content_parts: Content for the message
            **kwargs: Additional message fields
        """
        # Import here to avoid circular dependency
        from .roles import (
            AssistantMessage,
            SystemMessage,
            ToolMessage,
            UserMessage,
        )

        # Create message of appropriate type based on role
        message: Message
        if self._role == "user":
            message = UserMessage(*content_parts, **kwargs)
        elif self._role == "assistant":
            message = AssistantMessage(*content_parts, **kwargs)
        elif self._role == "system":
            message = SystemMessage(*content_parts, **kwargs)
        elif self._role == "tool":
            message = ToolMessage(*content_parts, **kwargs)
        else:
            raise ValueError(f"Unknown role: {self._role}")

        # Append to agent's main message list
        self._agent.messages.append(message)  # type: ignore[arg-type]

    @property
    def content(self) -> str | None:
        """Get content of first message as string, or None if no messages.

        Returns:
            Rendered content of first message, or None
        """
        from ..content import RenderMode

        # Filter agent's messages by role and return first message's content
        for msg in self._agent.messages:
            if msg.role == self._role:
                return msg.render(RenderMode.DISPLAY)
        return None

    def set(self, *content_parts: MessageContent, **kwargs) -> None:
        """Replace all messages of this role with a single new message.

        For system messages, also updates agent config with any LLM parameters.

        Args:
            *content_parts: Content for the new message
            **kwargs: Additional message fields and LLM config parameters
        """
        # Import here to avoid circular dependency
        from .roles import (
            AssistantMessage,
            SystemMessage,
            ToolMessage,
            UserMessage,
        )
        from ..config_types import AGENT_CONFIG_KEYS

        # For system messages, extract and apply config parameters
        message_kwargs = {}
        if self._role == "system":
            for key in list(kwargs.keys()):
                if key in AGENT_CONFIG_KEYS:
                    # Apply to agent config
                    setattr(self._agent.config, key, kwargs.pop(key))
                else:
                    message_kwargs[key] = kwargs.pop(key)
        else:
            message_kwargs = kwargs

        # Find and remove all messages with this role
        indices_to_remove = []
        for i, msg in enumerate(self._agent.messages):
            if msg.role == self._role:
                indices_to_remove.append(i)

        # Remove in reverse order to maintain indices
        for i in reversed(indices_to_remove):
            del self._agent.messages[i]

        # Create new message of appropriate type
        message: Message
        if self._role == "user":
            message = UserMessage(*content_parts, **message_kwargs)
        elif self._role == "assistant":
            message = AssistantMessage(*content_parts, **message_kwargs)
        elif self._role == "system":
            message = SystemMessage(*content_parts, **message_kwargs)
        elif self._role == "tool":
            message = ToolMessage(*content_parts, **message_kwargs)
        else:
            raise ValueError(f"Unknown role: {self._role}")

        # Add the new message
        self._agent.messages.append(message)  # type: ignore[arg-type]

    def __bool__(self) -> bool:
        """Check if any messages exist for this role.

        Returns:
            True if messages exist, False otherwise
        """
        for msg in self._agent.messages:
            if msg.role == self._role:
                return True
        return False


__all__ = ["FilteredMessageList"]
