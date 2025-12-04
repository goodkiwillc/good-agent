from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Protocol, TypeGuard, TypeVar, runtime_checkable

T = TypeVar("T")

if TYPE_CHECKING:
    from good_agent.content import RenderMode
    from good_agent.messages import Message


@runtime_checkable
class SupportsString(Protocol):
    """Protocol for objects that can be converted to a string."""

    def __str__(self) -> str: ...


@runtime_checkable
class SupportsLLM(Protocol):
    """Protocol for objects that can be used as LLM input."""

    def __llm__(self) -> str: ...


@runtime_checkable
class SupportsDisplay(Protocol):
    """Protocol for objects that can be rendered for display/UI."""

    def __display__(self) -> str: ...


@runtime_checkable
class SupportsRender(Protocol):
    """Protocol for objects that can be rendered with a template."""

    def render(self, **kwargs: Any) -> str: ...


def is_async_function(func: Callable | Any) -> TypeGuard[Callable[..., Awaitable[Any]]]:
    """Return True when *func* is an async function."""

    import inspect

    return inspect.iscoroutinefunction(func)


def is_sync_function(func: Callable | Any) -> TypeGuard[Callable[..., Any]]:
    """Return True when *func* is a synchronous function."""

    import inspect

    return callable(func) and not inspect.iscoroutinefunction(func)


def has_attribute(obj: Any, attr: str) -> bool:
    """Safely check whether *obj* exposes attribute *attr*."""

    return obj is not None and hasattr(obj, attr)


def is_render_mode_enum(obj: Any) -> TypeGuard[RenderMode]:
    """True when *obj* is a RenderMode enum value."""

    from good_agent.content import RenderMode

    return isinstance(obj, RenderMode)


def is_not_none(obj: T | None) -> TypeGuard[T]:
    """True when *obj* is not None."""

    return obj is not None


def is_dict_like(obj: Any) -> TypeGuard[dict[Any, Any]]:
    """True when *obj* supports basic dict operations."""

    return hasattr(obj, "__getitem__") and hasattr(obj, "get") and hasattr(obj, "keys")


def is_message(obj: Any) -> TypeGuard[Message]:
    """True when *obj* is a Message instance."""

    from good_agent.messages import Message

    return isinstance(obj, Message)


def safe_get_attr(obj: Any, attr: str, default: T) -> T | Any:
    """Return getattr(obj, attr, default) but protect against None."""

    if obj is None:
        return default
    return getattr(obj, attr, default)


def safe_get_dict_value(d: dict[Any, Any] | None, key: Any, default: T) -> T | Any:
    """Return dictionary value or default when *d* is None/missing key."""

    if d is None:
        return default
    return d.get(key, default)


__all__ = [
    "SupportsString",
    "SupportsLLM",
    "SupportsDisplay",
    "SupportsRender",
    "is_async_function",
    "is_sync_function",
    "has_attribute",
    "is_render_mode_enum",
    "is_not_none",
    "is_dict_like",
    "is_message",
    "safe_get_attr",
    "safe_get_dict_value",
]
