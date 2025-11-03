"""
Complete compatibility shim for litellm imports.

This module provides drop-in replacements for all litellm types and utils
used in the codebase, allowing gradual migration.
"""

# Re-export from our compat layer
from .compat import (
    Message,
    Usage,
    ModelResponse,
    ChatResponse,
    StreamChunk,
    Choices,
    StreamingChoices,
    CustomStreamWrapper,
    Router,
)

# Additional compatibility exports for specific litellm modules
__all__ = [
    "Message",
    "Usage", 
    "ModelResponse",
    "ChatResponse",
    "StreamChunk",
    "Choices",
    "StreamingChoices",
    "CustomStreamWrapper",
    "Router",
]
