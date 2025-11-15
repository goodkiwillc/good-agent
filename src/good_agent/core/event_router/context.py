"""Event context for passing state through handler chains.

This module contains the EventContext class, which is the central data structure
for event handler communication. It flows through handler chains, carrying
parameters, results, and control flow state.

CONTENTS:
- EventContext: Typed container for event data and state
- event_ctx: Context variable for accessing current context

THREAD SAFETY: EventContext instances are thread-safe via contextvars propagation.
Individual instances should not be modified concurrently by multiple handlers.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Generic

from .protocols import ApplyInterrupt, T_Parameters, T_Return


@dataclass(slots=True)
class EventContext(Generic[T_Parameters, T_Return]):
    """Event context that flows through handler chains with type safety and state management.

    PURPOSE: Provides a typed, immutable flow of data and state through event handler
    chains, enabling handlers to share results, errors, and control flow decisions.

    ROLE: Central carrier of event data that maintains consistency across async/sync
    boundaries and provides explicit mechanisms for handler communication and control.

    LIFECYCLE:
    1. Creation: EventRouter creates context with parameters and timestamp
    2. Handler Flow: Context passed through handlers in priority order
    3. State Updates: Handlers modify output, exception, or stop flags
    4. Completion: Context returned to caller with final state

    THREAD SAFETY: Thread-safe via contextvars propagation. Context object itself
    should not be modified concurrently by multiple handlers.

    TYPICAL USAGE:
        ```python
        # In event handler
        async def handle_process(ctx: EventContext[ProcessParams, ProcessResult]) -> None:
            params = ctx.parameters  # Typed access to input parameters
            result = await process_data(params["data"])
            ctx.output = result  # Set output for next handlers

            # Early termination
            if params.get("stop_early"):
                ctx.stop_with_output(result)


        # Check for early termination in subsequent handlers
        if ctx.should_stop:
            return  # Skip processing
        ```

    STATE MANAGEMENT:
    - parameters: Immutable input data from event dispatch
    - output: Mutable result accumulation, updated by handlers
    - exception: Captured error state for error handling workflows
    - _should_stop: Control flow flag for early termination
    - invocation_timestamp: Performance monitoring and debugging

    GENERIC TYPE PARAMETERS:
        T_Parameters: Type of input parameters (dict, TypedDict, or custom type)
        T_Return: Expected return type for type safety and IDE support

    PERFORMANCE NOTES:
    - Uses @dataclass(slots=True) for memory efficiency
    - Minimal overhead for context creation and propagation
    - Type annotations enable compile-time checking without runtime cost
    - Context propagation via contextvars is O(1) operation

    INTEGRATION POINTS:
    - EventRouter.apply_typed() creates typed contexts
    - Handler decorators receive context as first parameter
    - Current context accessible via EventRouter.ctx property
    - Context flows through broadcast targets transparently

    EXTENSION POINTS:
    - Custom context subclasses can add additional state
    - Typed contexts enable domain-specific data flow
    - Context metadata can be extended for debugging/monitoring

    RELATED CLASSES:
    - EventRouter: Creates and manages context flow
    - ApplyInterrupt: Exception for immediate context termination
    - TypedApply: Helper for type-safe context creation
    """

    parameters: T_Parameters
    """Input parameters for the event (read-only in handlers)."""

    output: T_Return | None = None
    """Output result accumulated by handlers (mutable)."""

    exception: BaseException | None = None
    """Captured exception for error handling (mutable)."""

    _should_stop: bool = False
    """Internal flag for early termination (use should_stop property)."""

    invocation_timestamp: float | None = None
    """Unix timestamp when event was dispatched (for debugging/monitoring)."""

    def stop_with_output(self, output: T_Return) -> None:
        """Stop the event chain and return the given output.

        This raises ApplyInterrupt to immediately stop execution.
        The output is preserved in the context.

        Args:
            output: The result to return from the event chain

        Raises:
            ApplyInterrupt: Always raised to stop handler execution
        """
        self.output = output
        self._should_stop = True
        raise ApplyInterrupt()

    def stop_with_exception(self, exception: BaseException) -> None:
        """Stop the event chain due to an exception.

        Unlike stop_with_output, this doesn't raise ApplyInterrupt.
        The handler should either raise the exception or return after calling this.
        The exception is preserved in the context for error handling.

        Args:
            exception: The exception that caused the stop
        """
        self.exception = exception
        self._should_stop = True
        # Note: Does NOT raise ApplyInterrupt - handler decides what to do

    @property
    def should_stop(self) -> bool:
        """Check if the event chain should stop.

        Returns:
            True if stop_with_output() or stop_with_exception() was called
        """
        return self._should_stop


# Context variable for current event context
event_ctx: contextvars.ContextVar[EventContext | None] = contextvars.ContextVar(
    "event_ctx", default=None
)
"""Context variable holding the current EventContext during handler execution.

This allows handlers to access the current context without explicit passing:

Example:
    ```python
    from good_agent.core.event_router.context import event_ctx

    def my_function():
        ctx = event_ctx.get()
        if ctx:
            print(f"Called with parameters: {ctx.parameters}")
    ```

THREAD SAFETY: contextvars.ContextVar is thread-safe and async-safe.
Each async task and thread has its own isolated value.
"""
