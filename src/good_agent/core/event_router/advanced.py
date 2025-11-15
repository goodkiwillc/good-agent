"""Advanced features for EventRouter.

This module contains optional advanced functionality that extends the core
EventRouter capabilities. It's not imported by default to keep the core
lightweight and minimize dependencies.

CONTENTS:
- TypedApply: Helper class for type-safe event application with cleaner syntax

USAGE:
    from good_agent.core.event_router.advanced import TypedApply
    from good_agent.core.event_router import EventRouter

    router = EventRouter()

    # Create typed helper
    typed_apply = router.typed(
        params_type=ProcessParams,
        return_type=ProcessResult
    )

    # Use with type safety
    ctx = await typed_apply.apply("process", data={"value": 42})
    result: ProcessResult | None = ctx.output

THREAD SAFETY: TypedApply is thread-safe as it only holds immutable references
to the EventRouter instance. All actual event processing is delegated to
EventRouter which handles its own thread safety.

PERFORMANCE: TypedApply adds minimal overhead - it's essentially a typed
wrapper that delegates to EventRouter.apply_typed() methods.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Generic

from .context import EventContext
from .protocols import EventName, T_Parameters, T_Return

if TYPE_CHECKING:
    from .core import EventRouter


class TypedApply(Generic[T_Parameters, T_Return]):
    """Helper class for type-safe event application with cleaner syntax.

    PURPOSE: Provides a convenient, type-safe interface for applying events
    without repeating type parameters on every call.

    ROLE: Thin wrapper around EventRouter.apply_typed() that encapsulates
    parameter and return types for repeated use with the same event signatures.

    TYPICAL USAGE:
        ```python
        # Define your types
        class ProcessParams(TypedDict):
            data: dict[str, Any]
            validate: bool

        class ProcessResult(TypedDict):
            processed: dict[str, Any]
            errors: list[str]

        # Create router and typed helper
        router = EventRouter()
        process = router.typed(
            params_type=ProcessParams,
            return_type=ProcessResult
        )

        # Use with full type safety
        ctx = await process.apply("process", data={"x": 1}, validate=True)
        result: ProcessResult | None = ctx.output

        # Or synchronously
        ctx = process.apply_sync("process", data={"x": 1}, validate=True)
        ```

    TYPE PARAMETERS:
        T_Parameters: Type of input parameters (TypedDict, dataclass, or dict)
        T_Return: Expected return type for handlers

    ATTRIBUTES:
        router: Reference to EventRouter instance
        params_type: Type hint for parameters (used by type checkers)
        return_type: Type hint for return value (used by type checkers)

    INTEGRATION POINTS:
        - Created via EventRouter.typed() method
        - Delegates to EventRouter.apply_typed() and apply_typed_sync()
        - Returns EventContext[T_Parameters, T_Return] for full type safety

    PERFORMANCE NOTES:
        - Zero overhead beyond a single method call delegation
        - Type parameters are only used by static type checkers (no runtime cost)
        - No additional data structures or processing

    RELATED CLASSES:
        - EventRouter: Creates TypedApply instances via typed() method
        - EventContext: Typed container returned by apply methods
    """

    def __init__(
        self,
        router: EventRouter,
        params_type: type[T_Parameters] | None = None,
        return_type: type[T_Return] | None = None,
    ):
        """Initialize TypedApply with router and type hints.

        Args:
            router: EventRouter instance to delegate to
            params_type: Type hint for parameters (optional, for type checkers)
            return_type: Type hint for return value (optional, for type checkers)
        """
        self.router = router
        self.params_type = params_type
        self.return_type = return_type

    async def apply(
        self, event: EventName, **kwargs: Any
    ) -> EventContext[T_Parameters, T_Return]:
        """Apply the event asynchronously with type safety.

        This method delegates to EventRouter.apply_typed() with the stored
        type parameters, providing a cleaner syntax for repeated typed calls.

        Args:
            event: Event name to dispatch
            **kwargs: Event parameters (must match params_type if specified)

        Returns:
            EventContext with typed parameters and return value

        Example:
            ```python
            typed_apply = router.typed(ProcessParams, ProcessResult)
            ctx = await typed_apply.apply("process", data={"x": 1})
            result: ProcessResult | None = ctx.output
            ```
        """
        return await self.router.apply_typed(
            event, self.params_type, self.return_type, **kwargs
        )

    def apply_sync(
        self, event: EventName, **kwargs: Any
    ) -> EventContext[T_Parameters, T_Return]:
        """Apply the event synchronously with type safety.

        This method delegates to EventRouter.apply_typed_sync() with the stored
        type parameters, providing a cleaner syntax for repeated typed calls.

        Args:
            event: Event name to dispatch
            **kwargs: Event parameters (must match params_type if specified)

        Returns:
            EventContext with typed parameters and return value

        Example:
            ```python
            typed_apply = router.typed(ProcessParams, ProcessResult)
            ctx = typed_apply.apply_sync("process", data={"x": 1})
            result: ProcessResult | None = ctx.output
            ```
        """
        return self.router.apply_typed_sync(
            event, self.params_type, self.return_type, **kwargs
        )
