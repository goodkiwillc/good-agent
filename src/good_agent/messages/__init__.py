"""Messages package - all message types and utilities."""

# Re-export base types
from .base import (
    IMAGE,
    Annotation,
    ImageDetail,
    Message,
    MessageContent,
    MessageRole,
)

# Re-export content types for backward compatibility
from ..content import RenderMode

# Re-export tools for backward compatibility
from ..tools import ToolCall, ToolResponse

# Re-export filtering
from .filtering import FilteredMessageList

# Re-export message list
from .message_list import MessageList, T_Message

# Re-export role-specific messages
from .roles import (
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
from .utilities import MessageFactory

__all__ = [
    # Base types
    "Annotation",
    "Message",
    "MessageRole",
    "ImageDetail",
    "IMAGE",
    "MessageContent",
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
