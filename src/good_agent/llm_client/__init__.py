"""
LLM Client - Fast, lightweight, extensible multi-provider client.

This module provides lazy-loaded access to LLM client components.
Import time is optimized to be <200ms.
"""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .router import Router
    from .types.chat import ChatRequest, ChatResponse, StreamChunk
    from .types.common import Message, Usage, ModelResponse

__all__ = [
    "Router",
    "ChatRequest",
    "ChatResponse",
    "StreamChunk",
    "Message",
    "Usage",
    "ModelResponse",
]

# Lazy loading cache
_cache: dict[str, Any] = {}


def __getattr__(name: str) -> Any:
    """Lazy load modules on first access."""
    if name in __all__:
        if name not in _cache:
            if name == "Router":
                from .router import Router
                _cache[name] = Router
            elif name in ("ChatRequest", "ChatResponse", "StreamChunk"):
                from . import types as _types_module
                _cache[name] = getattr(_types_module.chat, name)
            elif name in ("Message", "Usage", "ModelResponse"):
                from . import types as _types_module
                _cache[name] = getattr(_types_module.common, name)
        return _cache[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    """Return available attributes."""
    return list(__all__)
