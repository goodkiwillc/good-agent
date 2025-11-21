"""Type protocols, type definitions, and exceptions for the event router.

This module contains all type-level definitions used throughout the event router
package. It has no runtime dependencies on other event router modules, making it
safe to import from any module without circular dependency issues.

CONTENTS:
- Type variables and aliases for generic typing
- Protocol definitions for event handlers
- ApplyInterrupt exception for flow control

THREAD SAFETY: This module only contains type definitions and has no state,
so it is inherently thread-safe.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ParamSpec, Protocol, TypeVar, runtime_checkable

if TYPE_CHECKING:
    from good_agent.core.event_router.context import EventContext  # type: ignore[attr-defined]

# Type definitions
T_Parameters = TypeVar("T_Parameters")
"""Type variable for event handler parameters."""

T_Return = TypeVar("T_Return")
"""Type variable for event handler return values."""

EventName = str
"""Type alias for event names (strings)."""

EventPriority = int
"""Type alias for event handler priorities (integers, higher = earlier execution)."""

F = TypeVar("F", bound=Callable[..., Any])
"""Type variable for function decorators."""

P = ParamSpec("P")
"""ParamSpec for preserving function signatures."""

# Type for event handler functions that accept EventContext
EventHandlerFunc = Callable[["EventContext"], Any]
"""Type alias for event handler functions that accept an EventContext."""


# Protocol for methods that can be event handlers
@runtime_checkable
class EventHandlerMethod(Protocol):
    """Protocol for class methods that handle events.

    Event handlers are methods that receive an EventContext as their first
    parameter after self. They can be synchronous or asynchronous.

    Example:
        ```python
        class MyComponent:
            async def handle_event(self, ctx: EventContext[dict, str]) -> None:
                print(f"Received: {ctx.parameters}")
                ctx.output = "processed"
        ```
    """

    def __call__(self, ctx: EventContext[Any, Any], *args: Any, **kwargs: Any) -> Any:
        """Handle an event with the given context.

        Args:
            ctx: Event context containing parameters and state
            *args: Additional positional arguments
            **kwargs: Additional keyword arguments

        Returns:
            Any value (typically None for event handlers)
        """
        ...


@runtime_checkable
class EventHandler(Protocol):
    """Protocol for event handlers with metadata.

    Event handlers decorated with @on or registered via .on() receive
    configuration metadata stored in the _event_handler_config attribute.
    This metadata includes priority, event names, and other configuration.

    Example:
        ```python
        @on("my_event", priority=10)
        async def my_handler(ctx: EventContext) -> None:
            # Handler has _event_handler_config with priority=10
            pass
        ```
    """

    _event_handler_config: dict[str, Any]
    """Configuration metadata for the event handler."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Handler is callable.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Any value
        """
        ...


@runtime_checkable
class PredicateHandler(Protocol):
    """Protocol for event handlers with predicates.

    Handlers can have predicates that determine whether they should execute
    based on the event context. The predicate is a function that receives
    the EventContext and returns True if the handler should execute.

    Example:
        ```python
        def only_if_urgent(ctx: EventContext) -> bool:
            return ctx.parameters.get("urgent", False)

        @on("task", predicate=only_if_urgent)
        async def urgent_handler(ctx: EventContext) -> None:
            # Only executes if urgent=True in parameters
            pass
        ```
    """

    _predicate: Callable[[EventContext], bool]
    """Predicate function that determines if handler should execute."""

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Handler is callable.

        Args:
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Any value
        """
        ...


class ApplyInterrupt(Exception):
    """Exception to stop event chain execution.

    This exception can be raised to immediately stop the event handler chain
    and return control to the caller. It's typically raised by calling
    ctx.stop_with_output() within an event handler.

    Unlike normal exceptions, ApplyInterrupt is expected and handled gracefully
    by the event router. It's a control flow mechanism, not an error.

    Example:
        ```python
        async def early_termination_handler(ctx: EventContext[dict, str]) -> None:
            if ctx.parameters.get("skip_rest"):
                # Stop processing immediately and return result
                ctx.stop_with_output("early result")
                # ApplyInterrupt is raised here by stop_with_output()
        ```

    THREAD SAFETY: This is a standard exception class and is thread-safe.
    """

    pass
