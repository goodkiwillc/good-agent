"""Message management for Agent.

This module handles all message-related operations including appending,
replacing, filtering, and system message management.
"""

from __future__ import annotations

import logging
import warnings
from typing import TYPE_CHECKING, Any, Literal, overload

from good_agent.core.event_router import EventContext
from good_agent.core.types import URL
from good_agent.events import AgentEvents
from good_agent.messages import (
    AnnotationLike,
    AssistantMessage,
    FilteredMessageList,
    Message,
    MessageContent,
    MessageList,
    MessageRole,
    SystemMessage,
    ToolCall,
    ToolMessage,
    ToolResponse,
    UserMessage,
)
from good_agent.messages.store import put_message

if TYPE_CHECKING:
    from good_agent.agent import Agent

logger = logging.getLogger(__name__)


class MessageManager:
    """Manages message list operations, filtering, and validation.

    This manager centralizes all message-related functionality that was
    previously scattered throughout the Agent class.
    """

    def __init__(self, agent: Agent):
        """Initialize MessageManager with agent reference.

        Args:
            agent: The agent instance this manager belongs to
        """
        self.agent = agent

    @property
    def messages(self) -> MessageList[Message]:
        """All messages in the agent's conversation."""
        return self.agent._messages

    @property
    def user(self) -> FilteredMessageList[UserMessage]:
        """Filter messages to only user messages."""
        filtered = self.messages.filter(role="user")
        return FilteredMessageList(self.agent, "user", filtered)

    @property
    def assistant(self) -> FilteredMessageList[AssistantMessage]:
        """Filter messages to only assistant messages."""
        filtered = self.messages.filter(role="assistant")
        return FilteredMessageList(self.agent, "assistant", filtered)

    @property
    def tool(self) -> FilteredMessageList[ToolMessage]:
        """Filter messages to only tool messages."""
        filtered = self.messages.filter(role="tool")
        return FilteredMessageList(self.agent, "tool", filtered)

    @property
    def system(self) -> FilteredMessageList[SystemMessage]:
        """Filter messages to only system messages."""
        filtered = self.messages.filter(role="system")
        return FilteredMessageList(self.agent, "system", filtered)

    def _append_message(self, message: Message) -> None:
        """Internal method to append a message to the agent's message list.

        This centralized method ensures:
        - Proper agent reference is set
        - Message is stored in global store
        - Version is updated
        - Consistent event firing

        Args:
            message: Message to append
        """
        # Set agent reference on the message
        message._set_agent(self.agent)

        # Add to message list
        self.agent._messages.append(message)

        # Store in global message store
        put_message(message)

        # Update version
        self.agent._update_version()

        # Emit consistent MESSAGE_APPEND_AFTER event
        self.agent.do(AgentEvents.MESSAGE_APPEND_AFTER, message=message, agent=self.agent)

    def replace_message(self, index: int, new_message: Message) -> None:
        """Replace a message at the given index with a new message.

        This maintains message immutability - the old message still exists
        in previous versions, but the current thread uses the new message.

        Args:
            index: Index of message to replace
            new_message: New message to insert
        """
        if index < 0 or index >= len(self.agent._messages):
            raise IndexError(f"Message index {index} out of range")

        # Set agent reference on new message
        new_message._set_agent(self.agent)

        ctx = self.agent.events.apply_sync(
            AgentEvents.MESSAGE_REPLACE_BEFORE,
            index=index,
            output=new_message,
            agent=self.agent,
        )

        new_message = ctx.return_value or new_message

        # Replace the message
        self.agent._messages[index] = new_message

        # Store in global message store
        put_message(new_message)

        # Update version
        self.agent._update_version()

        # Emit message:replace event
        self.agent.do(
            AgentEvents.MESSAGE_REPLACE_AFTER,
            index=index,
            message=new_message,
            agent=self.agent,
        )

    def set_system_message(
        self,
        *content: MessageContent,
        message: SystemMessage | None = None,
    ) -> None:
        """Set or update the system message.

        Args:
            *content: Content parts for the system message
            message: Pre-created system message (if not using content)
        """
        # Create system message
        if content:
            message = self.agent.model.create_message(*content, role="system")

        if not message:
            raise ValueError("System message content is required")

        message._set_agent(self.agent)

        ctx: EventContext[Any, SystemMessage] = self.agent.events.typed(
            return_type=SystemMessage
        ).apply_sync(AgentEvents.MESSAGE_SET_SYSTEM_BEFORE, output=message, agent=self.agent)

        if ctx.return_value is not None:
            message = ctx.return_value

        # Check if we already have a system message
        if self.agent._messages:
            if isinstance(self.agent._messages[0], SystemMessage):
                # Replace existing system message using versioning-aware method
                self.agent._messages.replace_at(0, message)
            else:
                # Prepend system message using versioning-aware method
                self.agent._messages.prepend(message)
        else:
            # First message - use append (which is versioning-aware)
            self.agent._messages.append(message)

        # Store in global message store (redundant if versioning is active, but kept for compatibility)
        put_message(message)

        # Fire the AFTER event so components can modify the system message
        self.agent.do(AgentEvents.MESSAGE_SET_SYSTEM_AFTER, message=message, agent=self.agent)

        # Update version
        self.agent._update_version()

        if self.agent.config.print_messages and message.role in (
            self.agent.config.print_messages_role or [message.role]
        ):
            self.agent.print(message, mode=self.agent.config.print_messages_mode)

    @overload
    def append(self, content: Message) -> None: ...

    @overload
    def append(
        self,
        *content_parts: MessageContent,
        role: Literal["assistant"],
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        tool_calls: list[ToolCall] | None = None,
        reasoning: str | None = None,
        refusal: str | None = None,
        annotations: list[AnnotationLike] | None = None,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def append(
        self,
        *content_parts: MessageContent,
        role: Literal["tool"],
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        tool_call_id: str,
        tool_name: str | None = None,
        tool_response: ToolResponse | None = None,
        **kwargs: Any,
    ) -> None: ...

    @overload
    def append(
        self,
        *content_parts: MessageContent,
        role: MessageRole = "user",
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> None: ...

    def append(
        self,
        *content_parts: MessageContent,
        role: MessageRole = "user",
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Append a message to the conversation.

        Supports multiple content parts that will be concatenated with newlines:
        agent.append("First line", "Second line", "Third line")

        Args:
            *content_parts: Content to add to the message
            role: Message role (user, assistant, system, tool)
            context: Additional context for the message
            citations: List of citation URLs that correspond to [1], [2], etc. in content
            **kwargs: Additional message attributes
        """
        # Validate we have at least one content part
        if not content_parts:
            raise ValueError("At least one content part is required")

        if citations:
            citations = [URL(url) for url in citations]

        # Handle single Message object case
        if len(content_parts) == 1 and isinstance(content_parts[0], Message):
            message = content_parts[0]
        else:
            # Include citation_urls in the kwargs if provided
            if citations:
                kwargs["citation_urls"] = citations

            # For tool messages, ensure required fields are provided
            if role == "tool" and "tool_call_id" not in kwargs:
                logger.warning(
                    "Tool messages should include tool_call_id; using 'test_tool_call' as placeholder"
                    f" for message: {content_parts}"
                )
                kwargs["tool_call_id"] = kwargs.get("tool_call_id", "test_tool_call")
                kwargs["tool_name"] = kwargs.get("tool_name", "test_tool")

            message = self.agent.model.create_message(
                *content_parts,
                role=role,
                context=context,
                citations=citations,
                **kwargs,
            )

        # Add to conversation using centralized method
        self._append_message(message)

    def add_tool_response(
        self,
        content: str,
        tool_call_id: str,
        tool_name: str | None = None,
        **kwargs,
    ) -> None:
        """Add a tool response message to the conversation.

        .. deprecated:: 0.3.0
            Use ``append(content, role="tool", tool_call_id=...)`` instead.
            This method will be removed in version 1.0.0.

        Args:
            content: The tool response content
            tool_call_id: ID of the tool call this responds to
            tool_name: Name of the tool (optional)
            **kwargs: Additional message attributes
        """
        warnings.warn(
            "add_tool_response() is deprecated. "
            "Use append(content, role='tool', tool_call_id=...) instead. "
            "This method will be removed in version 1.0.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        # Forward to append for consistency
        self.append(
            content,
            role="tool",
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            **kwargs,
        )
