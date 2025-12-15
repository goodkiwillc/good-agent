"""Messages package - all message types and utilities."""

# Re-export base types
# Re-export content types for backward compatibility
from good_agent.content import RenderMode
from good_agent.messages.base import (
    IMAGE,
    Annotation,
    AnnotationLike,
    ImageDetail,
    Message,
    MessageContent,
    MessageRole,
    _get_render_stack,
)

# Re-export filtering
from good_agent.messages.filtering import FilteredMessageList

# Re-export message list
from good_agent.messages.message_list import MessageList, T_Message

# Re-export role-specific messages
from good_agent.messages.roles import (
    AssistantMessage,
    AssistantMessageStructuredOutput,
    CitationURL,
    SystemMessage,
    T_Output,
    T_ToolResponse,
    ToolMessage,
    UserMessage,
)

# Re-export utilities
from good_agent.messages.utilities import MessageFactory

# Re-export tools for backward compatibility
from good_agent.tools import ToolCall, ToolResponse

__all__ = [
    # Base types
    "Annotation",
    "AnnotationLike",
    "Message",
    "MessageRole",
    "ImageDetail",
    "IMAGE",
    "MessageContent",
    "_get_render_stack",
    # Role-specific messages
    "UserMessage",
    "SystemMessage",
    "AssistantMessage",
    "AssistantMessageStructuredOutput",
    "ToolMessage",
    # Message collections
    "MessageList",
    "FilteredMessageList",
    # Utilities
    "MessageFactory",
    # Type vars and aliases
    "T_Message",
    "T_Output",
    "T_ToolResponse",
    "CitationURL",
    # Tool types (re-exported for backward compatibility)
    "ToolCall",
    "ToolResponse",
    # Content types (re-exported for backward compatibility)
    "RenderMode",
]
