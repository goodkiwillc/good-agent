"""FilteredMessageList for role-specific message access."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Generic, TypeVar

from good_agent.messages.base import Message, MessageContent
from good_agent.messages.message_list import MessageList

if TYPE_CHECKING:
    from good_agent.agent import Agent

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

    def __init__(self, agent: Agent, role: str, messages: Iterable[T_Message] | None = None):
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
        # Role-specific validation
        if self._role == "tool" and "tool_call_id" not in kwargs:
            raise ValueError("tool_call_id is required for tool messages")

        # Always delegate to agent's append method for consistent event handling
        kwargs["role"] = self._role
        self._agent.append(*content_parts, **kwargs)

    @property
    def content(self) -> str | None:
        """Get content of first message as string, or None if no messages.

        Returns:
            Rendered content of first message, or None
        """
        from good_agent.content import RenderMode

        # Filter agent's messages by role and return first message's content
        for msg in self._agent.messages:
            if msg.role == self._role:
                return msg.render(RenderMode.DISPLAY)
        return None

    def set(self, *content_parts: MessageContent, **kwargs) -> None:
        """Set the system message (only available for system role).

        For system messages, updates both message content and agent config with
        any LLM parameters.

        Args:
            *content_parts: Content for the new message
            **kwargs: Additional message fields and LLM config parameters

        Raises:
            ValueError: If called on non-system role
        """
        if self._role != "system":
            raise ValueError(f"set() is only available for system messages, not {self._role}")

        # Import here to avoid circular dependency
        from good_agent.agent.config import AGENT_CONFIG_KEYS
        from good_agent.messages.roles import SystemMessage

        # Extract and apply config parameters
        message_kwargs = {}
        for key in list(kwargs.keys()):
            if key in AGENT_CONFIG_KEYS:
                # Apply to agent config
                setattr(self._agent.config, key, kwargs.pop(key))
            else:
                message_kwargs[key] = kwargs.pop(key)

        # Find and remove all system messages
        indices_to_remove = []
        for i, msg in enumerate(self._agent.messages):
            if msg.role == "system":
                indices_to_remove.append(i)

        # Remove in reverse order to maintain indices
        for i in reversed(indices_to_remove):
            del self._agent.messages[i]

        # Create new system message
        message = SystemMessage(*content_parts, **message_kwargs)

        # Add the new message
        self._agent.messages.append(message)  # type: ignore[arg-type]

    def __bool__(self) -> bool:
        """Check if any messages exist for this role.

        Returns:
            True if messages exist, False otherwise
        """
        return any(msg.role == self._role for msg in self._agent.messages)


__all__ = ["FilteredMessageList"]
