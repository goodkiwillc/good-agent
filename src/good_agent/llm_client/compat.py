"""
Compatibility layer for litellm types and interfaces.

Provides drop-in replacements for litellm imports to ease migration.
"""

from typing import Any, AsyncIterator
from .types.common import Message as _Message, Usage as _Usage, ModelResponse as _ModelResponse
from .types.chat import ChatResponse as _ChatResponse, StreamChunk as _StreamChunk
from .router import Router as _Router


# Type aliases for compatibility
Message = _Message
Usage = _Usage
ModelResponse = _ChatResponse  # ChatResponse is more specific
ChatResponse = _ChatResponse
StreamChunk = _StreamChunk


# Choices compatibility
class Choices:
    """Compatibility wrapper for litellm Choices."""
    
    def __init__(self, **kwargs: Any):
        self.finish_reason = kwargs.get("finish_reason", "stop")
        self.index = kwargs.get("index", 0)
        self.message = kwargs.get("message")
    
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class StreamingChoices:
    """Compatibility wrapper for litellm StreamingChoices."""
    
    def __init__(self, **kwargs: Any):
        self.finish_reason = kwargs.get("finish_reason")
        self.index = kwargs.get("index", 0)
        self.delta = kwargs.get("delta", {})
    
    def __getitem__(self, key: str) -> Any:
        return getattr(self, key)


class CustomStreamWrapper:
    """Compatibility wrapper for litellm CustomStreamWrapper."""
    
    def __init__(self, stream: AsyncIterator[StreamChunk]):
        self._stream = stream
    
    def __aiter__(self):
        return self
    
    async def __anext__(self) -> StreamChunk:
        return await self._stream.__anext__()


# Router alias
class Router(_Router):
    """
    Router with litellm-compatible interface.
    
    Extends our Router to provide compatibility methods.
    """
    
    async def acompletion(
        self,
        messages: list[Message] | list[dict[str, Any]],
        model: str | None = None,
        stream: bool = False,
        **kwargs: Any
    ) -> ChatResponse | CustomStreamWrapper:
        """
        Complete a chat request (litellm-compatible).
        
        Args:
            messages: List of messages (can be dicts or Message objects)
            model: Model to use
            stream: Whether to stream
            **kwargs: Additional parameters
        
        Returns:
            ChatResponse or CustomStreamWrapper
        """
        # Convert dict messages to Message objects
        if messages and isinstance(messages[0], dict):
            messages = [Message(**msg) if isinstance(msg, dict) else msg for msg in messages]
        
        return await super().acompletion(
            messages=messages,  # type: ignore
            model=model,
            stream=stream,
            **kwargs
        )


# Module-level functions for compatibility
_default_router: Router | None = None


def get_default_router() -> Router:
    """Get or create default router."""
    global _default_router
    if _default_router is None:
        _default_router = Router(
            models=["gpt-4o-mini"],
            api_key=None  # Will use env vars
        )
    return _default_router


async def acompletion(
    messages: list[Message] | list[dict[str, Any]],
    model: str = "gpt-4o-mini",
    **kwargs: Any
) -> ChatResponse:
    """Module-level completion function for compatibility."""
    router = get_default_router()
    return await router.acompletion(messages=messages, model=model, **kwargs)


async def completion(
    messages: list[Message] | list[dict[str, Any]],
    model: str = "gpt-4o-mini",
    **kwargs: Any
) -> ChatResponse:
    """Alias for acompletion."""
    return await acompletion(messages=messages, model=model, **kwargs)


# Export all compatibility types
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
    "acompletion",
    "completion",
]
