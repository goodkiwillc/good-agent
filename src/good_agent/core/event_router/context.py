"""Typed event contexts shared between handlers.

See ``examples/event_router/basic_usage.py`` for how contexts flow through
EventRouter chains.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Generic

from .protocols import ApplyInterrupt, T_Parameters, T_Return


@dataclass(slots=True)
class EventContext(Generic[T_Parameters, T_Return]):
    """Typed data container passed to each EventRouter handler.

    Carries parameters, mutable output/exception fields, and stop flags so
    handlers can cooperate safely across sync/async boundaries.
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
"""ContextVar exposing the current EventContext (see event_router examples)."""
