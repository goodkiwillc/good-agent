from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeGuard

if TYPE_CHECKING:
    from .content import RenderMode
    from .messages import Message


def is_async_function(func: Callable | Any) -> TypeGuard[Callable[..., Awaitable[Any]]]:
    """
    Type guard to check if a function is async.

    Args:
        func: Function to check

    Returns:
        True if the function is async, narrowing the type
    """
    import asyncio

    return asyncio.iscoroutinefunction(func)


def is_sync_function(func: Callable | Any) -> TypeGuard[Callable[..., Any]]:
    """
    Type guard to check if a function is synchronous.

    Args:
        func: Function to check

    Returns:
        True if the function is synchronous, narrowing the type
    """
    import asyncio

    return callable(func) and not asyncio.iscoroutinefunction(func)


def has_attribute(obj: Any, attr: str) -> bool:
    """
    Safe attribute check that handles None values.

    Args:
        obj: Object to check
        attr: Attribute name

    Returns:
        True if object has the attribute
    """
    return obj is not None and hasattr(obj, attr)


def is_render_mode_enum(obj: Any) -> TypeGuard["RenderMode"]:
    """
    Type guard to check if an object is a RenderMode enum.

    Args:
        obj: Object to check

    Returns:
        True if object is a RenderMode enum
    """
    from .content import RenderMode

    return isinstance(obj, RenderMode)


def is_not_none[T](obj: T | None) -> TypeGuard[T]:
    """
    Type guard to check that an object is not None.

    Args:
        obj: Object to check

    Returns:
        True if object is not None, narrowing the type
    """
    return obj is not None


def is_dict_like(obj: Any) -> TypeGuard[dict[Any, Any]]:
    """
    Type guard to check if an object is dict-like.

    Args:
        obj: Object to check

    Returns:
        True if object has dict-like interface
    """
    return hasattr(obj, "__getitem__") and hasattr(obj, "get") and hasattr(obj, "keys")


def is_message(obj: Any) -> TypeGuard["Message"]:
    """
    Type guard to check if an object is a Message instance.

    Args:
        obj: Object to check

    Returns:
        True if object is a Message
    """
    from .messages import Message

    return isinstance(obj, Message)


def safe_get_attr[T](obj: Any, attr: str, default: T) -> T | Any:
    """
    Safely get an attribute from an object.

    Args:
        obj: Object to get attribute from
        attr: Attribute name
        default: Default value if attribute doesn't exist

    Returns:
        Attribute value or default
    """
    if obj is None:
        return default
    return getattr(obj, attr, default)


def safe_get_dict_value[T](d: dict[Any, Any] | None, key: Any, default: T) -> T | Any:
    """
    Safely get a value from a dictionary.

    Args:
        d: Dictionary to get value from
        key: Key to look up
        default: Default value if key doesn't exist

    Returns:
        Value or default
    """
    if d is None:
        return default
    return d.get(key, default)
