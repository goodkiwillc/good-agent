"""Decorator implementations for event handling.

This module provides the @on, @emit, and @typed_on decorators that enable
declarative event handling with lifecycle phases, priorities, and predicates.

CONTENTS:
- on(): Decorator for registering event handlers with metadata
- emit: Decorator class for method lifecycle events (BEFORE/AFTER/ERROR/FINALLY)
- emit_event(): Function-style emit decorator (backward compatibility)
- typed_on(): Type-safe variant of @on decorator
- EventHandlerDecorator: Type alias for handler decorators

THREAD SAFETY: Decorators themselves are stateless and thread-safe.
Handler registration (which happens during class initialization) is
thread-safe via HandlerRegistry's locking.

LIFECYCLE PHASES: The @emit decorator supports Observable-style lifecycle phases:
- BEFORE: Execute before method body
- AFTER: Execute after successful method completion
- ERROR: Execute when method raises exception
- FINALLY: Execute always (success or failure)
"""

from __future__ import annotations

import functools
import inspect
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, TypeVar, cast

from good_agent.core.event_router.context import EventContext
from good_agent.core.event_router.protocols import ApplyInterrupt, EventName, F
from good_agent.core.event_router.registration import LifecyclePhase

if TYPE_CHECKING:
    from good_agent.core.event_router.core import EventRouter  # pragma: no cover

# Type variable for methods (includes self parameter)
T_Method = TypeVar("T_Method", bound=Callable[..., object])
EventContextAwaitable = Awaitable[EventContext[dict[str, Any], Any]]


def on(
    *events: EventName,
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """Attach event metadata used by EventRouter/Agent auto-registration.

    Methods decorated with ``@on`` must accept an ``EventContext`` and will be
    subscribed with the given priority/predicate. Usage is shown in
    ``examples/events/basic_events.py``.
    """

    def decorator(fn: F) -> F:
        # Store configuration on the function
        # This metadata is read by EventRouter._auto_register_handlers
        fn._event_handler_config = {  # type: ignore[attr-defined]
            "events": events,
            "priority": priority,
            "predicate": predicate,
        }
        return fn

    return decorator


class emit:
    """
    Class that provides both phase constants and decorator functionality.
    Matches Observable's emit API while maintaining backward compatibility.

    Usage:
        # Observable-style with phase constant
        @emit(emit.BEFORE | emit.AFTER)
        def method(self): ...

        # Custom event name with default phases
        @emit("custom_event")
        def method(self): ...

        # Custom event name with explicit phases
        @emit("custom_event", phases=emit.BEFORE | emit.ERROR)
        def method(self): ...

        # Without parentheses (uses method name and default phases)
        @emit
        def method(self): ...
    """

    # Phase constants
    BEFORE = LifecyclePhase.BEFORE
    AFTER = LifecyclePhase.AFTER
    ERROR = LifecyclePhase.ERROR
    FINALLY = LifecyclePhase.FINALLY

    def __new__(
        cls,
        lifecycle: LifecyclePhase | str | Callable[..., Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Handle special case of @emit without parentheses."""
        # If lifecycle is a callable (function), it means @emit was used without parentheses
        if callable(lifecycle) and not isinstance(lifecycle, (LifecyclePhase, str)):
            # Create a default emit instance and immediately apply it
            instance = object.__new__(cls)
            emit.__init__(
                instance,
                lifecycle=LifecyclePhase.BEFORE | LifecyclePhase.AFTER,
                event=None,
                include_args=True,
                include_result=True,
            )
            return instance(lifecycle)  # Apply decorator to the function
        else:
            # Normal instantiation
            return object.__new__(cls)

    def __init__(
        self,
        lifecycle: LifecyclePhase | str,
        event: str | None = None,
        phases: LifecyclePhase | list[LifecyclePhase] | None = None,
        include_args: bool = True,
        include_result: bool = True,
    ):
        """
        Initialize with lifecycle phases.

        Args:
            lifecycle: The lifecycle phases to emit events for, OR the event name (if string)
            event: Optional event name (if lifecycle is a LifecyclePhase)
            phases: Optional phases (if lifecycle is a string/event name)
            include_args: Include method arguments in events
            include_result: Include method result in AFTER event
        """
        # Handle different call patterns
        if isinstance(lifecycle, str):
            # Pattern: @emit("event_name") or @emit("event_name", phases=...)
            self.event: str | None = lifecycle
            if phases is not None:
                # Convert list to Flag if needed
                if isinstance(phases, list):
                    combined = phases[0]
                    for phase in phases[1:]:
                        combined = combined | phase
                    self.lifecycle = combined
                else:
                    self.lifecycle = phases
            else:
                # Default to BEFORE | AFTER
                self.lifecycle = LifecyclePhase.BEFORE | LifecyclePhase.AFTER
        else:
            # Pattern: @emit(LifecyclePhase.BEFORE | LifecyclePhase.AFTER, "event_name")
            self.lifecycle = lifecycle
            self.event = event

        self.include_args = include_args
        self.include_result = include_result

    def __call__(self, func: T_Method) -> T_Method:
        """
        Decorator that automatically emits events around method execution.

        Args:
            event: Event name (if None, uses method name as event)
            phases: Which lifecycle phases to emit (default: BEFORE | AFTER)
                    Can be a LifecyclePhase Flag enum or list of phases
            include_result: Include method result in AFTER event
            include_args: Include method arguments in events

        Examples:
            @emit("user:create")
            def create_user(self, name: str):
                return User(name=name)

            @emit("process", phases=LifecyclePhase.BEFORE | LifecyclePhase.ERROR)
            async def process_data(self, data):
                pass

            # Also supports list syntax for compatibility
            @emit("process", phases=[LifecyclePhase.ERROR])
            async def process_data(self, data):
                pass
        """
        _root = self

        # Determine event name (func.__name__ is always available)
        event_name = self.event if self.event is not None else func.__name__

        # Check if it's an async function
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                # Import here to avoid circular dependency
                from good_agent.core.event_router.core import EventRouter

                # Ensure self is EventRouter
                if not isinstance(self, EventRouter):
                    return await cast(
                        Awaitable[Any],
                        func(self, *args, **kwargs),
                    )

                router: EventRouter = self

                method_args = {}
                if _root.include_args:
                    sig = inspect.signature(func)
                    bound = sig.bind(self, *args, **kwargs)
                    bound.apply_defaults()
                    method_args = dict(bound.arguments)
                    method_args.pop("self", None)

                result = None
                error = None

                try:
                    # BEFORE phase
                    if _root.lifecycle & LifecyclePhase.BEFORE:
                        ctx = await cast(
                            EventContextAwaitable,
                            router.apply_async(f"{event_name}:before", **method_args),
                        )
                        # Note: EventRouter does NOT modify method parameters
                        # The output is available but doesn't affect the method execution

                    # Execute method with original parameters
                    result = await cast(
                        Awaitable[Any],
                        func(self, *args, **kwargs),
                    )

                    # AFTER phase
                    if _root.lifecycle & LifecyclePhase.AFTER:
                        after_args = method_args.copy()
                        if _root.include_result:
                            after_args["result"] = result
                        ctx = await cast(
                            EventContextAwaitable,
                            router.apply_async(f"{event_name}:after", **after_args),
                        )
                        if ctx.output is not None:
                            result = ctx.output

                    return result

                except Exception as e:
                    error = e
                    # ERROR phase
                    if _root.lifecycle & LifecyclePhase.ERROR:
                        error_args = method_args.copy()
                        error_args["error"] = e
                        try:
                            ctx = await cast(
                                EventContextAwaitable,
                                router.apply_async(f"{event_name}:error", **error_args),
                            )
                            if ctx.output is not None:
                                return ctx.output
                        except ApplyInterrupt:
                            raise e from None
                    raise

                finally:
                    # FINALLY phase
                    if _root.lifecycle & LifecyclePhase.FINALLY:
                        finally_args = method_args.copy()
                        if _root.include_result and result is not None:
                            finally_args["result"] = result
                        if error is not None:
                            finally_args["error"] = error
                        # Use apply_async for async methods to ensure completion
                        await cast(
                            EventContextAwaitable,
                            router.apply_async(f"{event_name}:finally", **finally_args),
                        )

            return cast(T_Method, async_wrapper)

        else:

            @functools.wraps(func)
            def sync_wrapper(self, *args, **kwargs):
                # Import here to avoid circular dependency
                from good_agent.core.event_router.core import EventRouter

                # Ensure self is EventRouter
                if not isinstance(self, EventRouter):
                    return func(self, *args, **kwargs)

                router: EventRouter = self

                method_args = {}
                if _root.include_args:
                    sig = inspect.signature(func)
                    bound = sig.bind(self, *args, **kwargs)
                    bound.apply_defaults()
                    method_args = dict(bound.arguments)
                    method_args.pop("self", None)

                result = None
                error = None

                try:
                    # BEFORE phase
                    if _root.lifecycle & LifecyclePhase.BEFORE:
                        ctx = router.apply_sync(f"{event_name}:before", **method_args)
                        # Note: EventRouter does NOT modify method parameters
                        # The output is available but doesn't affect the method execution

                    # Execute method with original parameters
                    result = func(self, *args, **kwargs)

                    # AFTER phase
                    if _root.lifecycle & LifecyclePhase.AFTER:
                        after_args = method_args.copy()
                        if _root.include_result:
                            after_args["result"] = result
                        ctx = router.apply_sync(f"{event_name}:after", **after_args)
                        if ctx.output is not None:
                            result = ctx.output

                    return result

                except Exception as e:
                    error = e
                    # ERROR phase
                    if _root.lifecycle & LifecyclePhase.ERROR:
                        error_args = method_args.copy()
                        error_args["error"] = e
                        try:
                            ctx = router.apply_sync(f"{event_name}:error", **error_args)
                            if ctx.output is not None:
                                return ctx.output
                        except ApplyInterrupt:
                            raise e from None
                    raise

                finally:
                    # FINALLY phase
                    if _root.lifecycle & LifecyclePhase.FINALLY:
                        finally_args = method_args.copy()
                        if _root.include_result and result is not None:
                            finally_args["result"] = result
                        if error is not None:
                            finally_args["error"] = error
                        router.do(f"{event_name}:finally", **finally_args)

            return cast(T_Method, sync_wrapper)


def emit_event(
    event: str | None = None,
    phases: LifecyclePhase | None = None,
    include_args: bool = True,
    include_result: bool = True,
) -> emit:
    """
    Backward-compatible function decorator for emit.

    This function provides compatibility with code that uses the function-style
    emit_event decorator instead of the class-style emit decorator.

    Args:
        event: Event name (if None, uses method name)
        phases: Which lifecycle phases to emit (default: BEFORE | AFTER)
        include_args: Include method arguments in events
        include_result: Include method result in AFTER event

    Example:
        @emit_event("process", phases=LifecyclePhase.BEFORE | LifecyclePhase.ERROR)
        def process_data(self, data):
            pass
    """
    # Default to BEFORE | AFTER if no phases specified
    if phases is None:
        phases = LifecyclePhase.BEFORE | LifecyclePhase.AFTER

    # Create and return an emit instance
    return emit(
        lifecycle=phases,
        event=event,
        include_args=include_args,
        include_result=include_result,
    )


def typed_on(
    *events: EventName,
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[F], F]:
    """
    Type-safe version of the @on decorator with improved type hints.

    This is functionally identical to @on but provides better type checking
    for IDEs and type checkers that struggle with the overloaded version.

    Usage:
        class MyAgent(EventRouter):
            @typed_on("agent:init")
            async def _handle_init(
                self,
                ctx: EventContext[dict[str, Any], None]
            ) -> None:
                agent = ctx.parameters.get("agent")
                # Type checker knows ctx.parameters is a dict
    """
    return on(*events, priority=priority, predicate=predicate)


# Helper type alias for cleaner event handler signatures
EventHandlerDecorator = Callable[[F], F]
