"""Typed event contexts shared between handlers.

See ``examples/event_router/basic_usage.py`` for how contexts flow through
EventRouter chains.
"""

from __future__ import annotations

import contextvars
from dataclasses import dataclass
from typing import Generic, TypeAlias, TypeVar

from good_agent.core.event_router.protocols import (
    ApplyInterrupt,
    T_Parameters,
    T_Return,
)

T_Result = TypeVar("T_Result")
EventResult: TypeAlias = "T_Result | BaseException"


@dataclass(slots=True)
class EventContext(Generic[T_Parameters, T_Return]):
    """Typed data container passed to each EventRouter handler.

    Carries parameters, mutable output/exception fields, and stop flags so
    handlers can cooperate safely across sync/async boundaries.
    """

    parameters: T_Parameters
    """Input parameters for the event (read-only in handlers)."""

    output: EventResult[T_Return] | None = None
    """Output or exception accumulated by handlers (mutable)."""

    exception: BaseException | None = None
    """Captured exception for error handling (mutable)."""

    event: str | None = None
    """Event name associated with this context (for handler inspection)."""

    _should_stop: bool = False
    """Internal flag for early termination (use should_stop property)."""

    _stopped_with_exception: bool = False
    """Whether stop_with_exception/stop(exception=...) was invoked."""

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
        self.output = exception  # Preserve legacy behavior inspected by tests
        self._should_stop = True
        self._stopped_with_exception = True
        # Note: Does NOT raise ApplyInterrupt - handler decides what to do

    def stop(
        self,
        *,
        output: T_Return | None = None,
        exception: BaseException | None = None,
    ) -> None:
        """Backward-compatible helper allowing ctx.stop(output=...) usage.

        Args:
            output: Optional result to return (raises ApplyInterrupt)
            exception: Optional exception object to record (no interrupt)

        Raises:
            ValueError: If both output and exception are provided
        """

        if output is not None and exception is not None:
            raise ValueError("Provide either output or exception, not both")

        if exception is not None:
            self.stop_with_exception(exception)
            return

        if output is not None:
            self.stop_with_output(output)
            return

        # No payload, just flag future handlers to stop early
        self._should_stop = True

    @property
    def should_stop(self) -> bool:
        """Check if the event chain should stop.

        Returns:
            True if stop_with_output() or stop_with_exception() was called
        """
        return self._should_stop

    @property
    def stopped(self) -> bool:
        """Backward-compatible alias for should_stop."""

        return self.should_stop

    @property
    def stopped_with_exception(self) -> bool:
        """Indicate whether stop_with_exception / stop(exception=...) was invoked."""

        return self._stopped_with_exception

    @property
    def return_value(self) -> T_Return | None:
        """Typed accessor that hides stored exceptions from consumers.

        Returns:
            The declared return type when available, otherwise ``None`` if no output
            was produced or when the payload holds an exception.
        """

        output = self.output
        if isinstance(output, BaseException):
            return None
        return output


# Context variable for current event context
event_ctx: contextvars.ContextVar[EventContext | None] = contextvars.ContextVar(
    "event_ctx", default=None
)
"""ContextVar exposing the current EventContext (see event_router examples)."""
