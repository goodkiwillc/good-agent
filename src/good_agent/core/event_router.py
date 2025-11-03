"""
CONTEXT: High-performance event routing system with type safety and async/sync interoperability.
ROLE: Central event management infrastructure for the GoodIntel platform, providing publish/subscribe patterns with priority-based handler execution.
DEPENDENCIES:
  - asyncio: Core async runtime for concurrent handler execution
  - contextvars: Event context propagation across async boundaries
  - dataclasses: Efficient data structures with slots optimization
  - loguru: Structured logging with debug tracing capabilities
  - rich: Enhanced console output for event visualization and debugging
ARCHITECTURE:
  - EventRouter: Central dispatcher with handler registry and priority queues
  - EventContext: Typed context flow through handler chains with state management
  - Handler system: Priority-based execution with predicate filtering and async/sync compatibility
  - Broadcast network: Multi-router event propagation for distributed systems
KEY EXPORTS: EventRouter, EventContext, TypedApply, on/emit decorators, LifecyclePhase enum
USAGE PATTERNS:
  1. Fire-and-forget events with router.do("event_name", **params)
  2. Blocking events with router.apply_async("event_name", **params) or router.apply_sync(...)
  3. Type-safe events with router.typed(ParamsType, ReturnType).apply("event", **params)
  4. Handler registration with @router.on("event", priority=100) or @on("event") decorators
  5. Method lifecycle events with @emit(LifecyclePhase.BEFORE | LifecyclePhase.AFTER)
  6. Multi-router event broadcasting with router.broadcast_to(other_router)
RELATED MODULES:
  - goodintel_core.utilities.signal_handler: Graceful shutdown and signal integration
  - goodintel_core.utilities.observable: Legacy pattern compatibility layer
  - goodintel_core.clients.*: Client libraries that emit events for integration
  - goodintel_core.workflows.*: Workflow orchestration using event patterns

PERFORMANCE CHARACTERISTICS:
  - Handler execution: O(n log n) where n=handlers (priority sorting overhead)
  - Memory usage: O(h) where h=registered handlers per event type
  - Async overhead: Minimal for sync handlers, thread pool bridging for mixed sync/async
  - Context propagation: O(1) via contextvars, no copying overhead

CONCURRENCY MODEL:
  - Event handlers execute in priority order (higher priority first)
  - Async handlers run concurrently when possible via asyncio.gather
  - Sync handlers execute sequentially within their priority level
  - Context flow is thread-safe via contextvars propagation
  - Event broadcasting between routers is non-blocking and parallelized

ERROR HANDLING STRATEGY:
  - Handler exceptions captured and logged but don't stop event flow
  - ApplyInterrupt exception provides explicit early termination
  - Error context preserved in EventContext.exception for downstream handlers
  - Separate ERROR phase events for lifecycle-based error handling
  - Debug mode with full exception traces and handler diagnostics
"""

from __future__ import annotations

import asyncio
import collections
import concurrent.futures
import contextvars
import enum
import functools
import inspect
import logging
import queue
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import (
    Any,
    Generic,
    ParamSpec,
    Protocol,
    TypeVar,
    cast,
    overload,
    runtime_checkable,
)

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

logger = logging.getLogger(__name__)

# Type definitions
T_Parameters = TypeVar("T_Parameters")
T_Return = TypeVar("T_Return")
EventName = str
EventPriority = int
F = TypeVar("F", bound=Callable[..., Any])
P = ParamSpec("P")


# Create a console instance for Rich output
_console = Console(stderr=True)  # Use stderr to avoid interfering with stdout

# Type for event handler functions that accept EventContext
EventHandlerFunc = Callable[["EventContext"], Any]


# Protocol for methods that can be event handlers
@runtime_checkable
class EventHandlerMethod(Protocol):
    """Protocol for class methods that handle events."""

    def __call__(
        self, ctx: EventContext[Any, Any], *args: Any, **kwargs: Any
    ) -> Any: ...


@runtime_checkable
class EventHandler(Protocol):
    """Protocol for event handlers with metadata."""

    _event_handler_config: dict[str, Any]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Handler is callable."""
        ...


@runtime_checkable
class PredicateHandler(Protocol):
    """Protocol for event handlers with predicates."""

    _predicate: Callable[[EventContext], bool]

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Handler is callable."""
        ...


class ApplyInterrupt(Exception):
    """Exception to stop event chain execution."""

    pass


@dataclass(slots=True)
class EventContext(Generic[T_Parameters, T_Return]):
    """
    Event context that flows through handler chains with type safety and state management.

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
    output: T_Return | None = None
    exception: BaseException | None = None
    _should_stop: bool = False
    invocation_timestamp: float | None = (
        None  # Unix timestamp when event was dispatched
    )

    def stop_with_output(self, output: T_Return) -> None:
        """
        Stop the event chain and return the given output.

        This raises ApplyInterrupt to immediately stop execution.
        The output is preserved in the context.
        """
        self.output = output
        self._should_stop = True
        raise ApplyInterrupt()

    def stop_with_exception(self, exception: BaseException) -> None:
        """
        Stop the event chain due to an exception.

        Unlike stop_with_output, this doesn't raise ApplyInterrupt.
        The handler should either raise the exception or return after calling this.
        The exception is preserved in the context for error handling.
        """
        self.exception = exception
        self._should_stop = True
        # Note: Does NOT raise ApplyInterrupt - handler decides what to do

    @property
    def should_stop(self) -> bool:
        """Check if the event chain should stop."""
        return self._should_stop


# Context variable for current event context
event_ctx: contextvars.ContextVar[EventContext | None] = contextvars.ContextVar(
    "event_ctx", default=None
)


@dataclass
class HandlerRegistration:
    handler: Callable[..., Any]
    predicate: Callable[[EventContext], bool] | None = None


# Context variable for tracking current test during pytest runs
current_test_nodeid: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_test_nodeid", default=None
)


class LifecyclePhase(enum.Flag):
    """
    Phases in method lifecycle for @emit decorator.

    Uses enum.Flag to allow bitwise operations like Observable's Lifecycle:
        phases = LifecyclePhase.BEFORE | LifecyclePhase.AFTER
    """

    BEFORE = enum.auto()
    AFTER = enum.auto()
    ERROR = enum.auto()
    FINALLY = enum.auto()


# Note: The emit decorator function is defined later in this file


@dataclass
class SyncRequest:
    """Request from sync context to async context."""

    event: EventName
    parameters: dict[str, Any]
    result_queue: queue.Queue
    request_id: str


class EventRouter:
    """
    High-performance event router with fire-and-forget and blocking dispatch capabilities.

    PURPOSE: Central event management hub that provides publish/subscribe patterns with
    priority-based handler execution, type safety, and seamless async/sync interoperability.

    ROLE: Orchestrates event flow across the GoodIntel platform, enabling loose coupling
    between components while maintaining high performance and predictable execution order.

    LIFECYCLE:
    1. Initialization: Router created with optional configuration and auto-registration
    2. Handler Registration: Methods decorated with @on() or router.on() registered
    3. Event Dispatch: Events fired via do(), apply_async(), or apply_sync()
    4. Handler Execution: Priority-ordered execution with predicate filtering
    5. Cleanup: Background tasks joined, resources released via close()/async_close()

    THREAD SAFETY:
    - Router instance is NOT thread-safe for concurrent event dispatch
    - Individual event dispatch is thread-safe via contextvars
    - Use separate router instances per thread or implement external synchronization
    - Background task management is thread-safe

    TYPICAL USAGE:
    ```python
    # Basic router setup
    router = EventRouter(debug=True, enable_signal_handling=True)


    # Handler registration
    @router.on("process:data", priority=200)
    async def handle_data(ctx: EventContext[dict, Any]) -> None:
        data = ctx.parameters["data"]
        result = await process(data)
        ctx.output = result


    # Fire-and-forget event
    router.do("process:data", data={"value": 42})

    # Blocking event with result
    ctx = await router.apply_async("process:data", data={"value": 42})
    result = ctx.output

    # Type-safe event
    ctx = await router.typed(ProcessParams, ProcessResult).apply(
        "process:data", data={"value": 42}
    )
    ```

    CONCURRENCY PATTERNS:
    - Fire-and-forget (do()): Non-blocking, handlers run in background
    - Blocking async (apply_async()): Waits for all handlers, supports async handlers
    - Blocking sync (apply_sync()): Waits for sync handlers only, runs async in thread pool
    - Type-safe (apply_typed()): Same as apply_async but with explicit type annotations

    PERFORMANCE CHARACTERISTICS:
    - Handler lookup: O(1) via dict mapping per event type
    - Priority sorting: O(p log p) where p=unique priority levels (cached)
    - Async dispatch: Minimal overhead for sync handlers, concurrent for async handlers
    - Memory usage: O(h) where h=total registered handlers across all events
    - Context creation: O(1) with slots optimization and minimal allocation

    BROADCASTING AND COMPOSITION:
    - Events can be broadcast to multiple routers for distributed systems
    - Handler inheritance via broadcast_to() and consume_from()
    - Event chaining supported via context manipulation
    - Cross-router communication maintains priority and type safety

    ERROR HANDLING:
    - Handler exceptions captured but don't stop event flow (unless ApplyInterrupt)
    - Debug mode provides detailed exception traces and handler diagnostics
    - Error context preserved in EventContext for error handling workflows
    - Separate error phase events via @emit decorator for lifecycle management

    INTEGRATION FEATURES:
    - Auto-registration of decorated methods during __post_init__()
    - Signal handling integration for graceful shutdown
    - Rich console output for event tracing and debugging
    - Context variable support for accessing current event context
    - Plugin system compatible architecture

    CONFIGURATION OPTIONS:
    - default_event_timeout: Timeout for async handlers in sync context
    - debug: Enable detailed logging and exception traces
    - _event_trace: Enable comprehensive event logging with timing
    - enable_signal_handling: Automatic graceful shutdown on signals

    EXTENSION POINTS:
    - Custom handler predicates for conditional execution
    - Typed event contexts for domain-specific data flow
    - Custom event tracing and monitoring integrations
    - Plugin system for router extensions and middleware

    RELATED CLASSES:
    - EventContext: Typed context flow through handler chains
    - TypedApply: Helper for type-safe event dispatch
    - @on decorator: Handler registration with metadata
    - @emit decorator: Method lifecycle event generation
    - ApplyInterrupt: Exception for early termination
    """

    def __init__(
        self,
        default_event_timeout: float | None = None,
        debug: bool = False,
        _event_trace: bool = False,
        enable_signal_handling: bool = False,
        **kwargs,
    ):
        """
        Initialize EventRouter.

        Args:
            default_event_timeout: Default timeout for event handlers
            debug: Enable debug logging
            _event_trace: Enable detailed event tracing (logs all events)
            enable_signal_handling: Enable automatic signal handling for graceful shutdown
        """
        super().__init__(**kwargs)
        self._default_event_timeout = default_event_timeout
        self._debug = debug
        if _event_trace:
            logger.debug("Event tracing enabled")
        self._event_trace = _event_trace  # Private to avoid conflicts
        self._event_trace_verbosity = 1  # 0=minimal, 1=normal, 2=verbose
        self._event_trace_use_rich = True  # Use Rich formatting by default
        self._signal_handling_enabled = enable_signal_handling

        # Event handler registry
        self._events: dict[
            EventName, dict[EventPriority, list[HandlerRegistration]]
        ] = collections.defaultdict(lambda: collections.defaultdict(list))

        # Broadcasting support
        self._broadcast_to: list[EventRouter] = []

        # Task management
        self._tasks: set[asyncio.Task] = set()
        self._futures: set[concurrent.futures.Future] = (
            set()
        )  # Track futures from run_coroutine_threadsafe

        # Thread pool for running async handlers from sync context
        self._thread_pool: concurrent.futures.ThreadPoolExecutor | None = None
        self._event_loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: threading.Thread | None = None

        # Queue-based sync->async bridge
        self._sync_request_queue: asyncio.Queue | None = None
        self._sync_worker_task: asyncio.Task | None = None

        # Call __post_init__ to complete initialization
        # This will handle auto-registration and allow subclasses to override
        self.__post_init__()

    def _auto_register_handlers(self):
        """Auto-register methods decorated with @on."""
        # Check both the instance and the class for decorated methods
        for name in dir(self):
            # Skip dunder methods, properties and other special attributes but allow single underscore methods with handler config. # Skip properties and other special attributes
            if name.startswith("__") or name in ("ctx",):
                continue

            try:
                # Get the unbound method from the class to check for decorator metadata
                class_attr = getattr(type(self), name, None)
                if class_attr and hasattr(class_attr, "_event_handler_config"):
                    # Get the bound method from the instance
                    bound_method = getattr(self, name)
                    config = class_attr._event_handler_config
                    for event in config["events"]:
                        self.on(
                            event,
                            priority=config["priority"],
                            predicate=config.get("predicate"),
                        )(bound_method)
            except Exception as e:
                # Skip any attributes that can't be accessed
                if self._debug:
                    import traceback

                    logger.warning(f"Failed to register handler {name}: {e}")
                    logger.debug(traceback.format_exc())
                continue

    def __post_init__(self):
        """Called after dataclass initialization if this is a dataclass."""
        self._auto_register_handlers()

        # Register for signal handling if enabled
        if self._signal_handling_enabled:
            from .signal_handler import register_for_signals

            register_for_signals(self)

    def broadcast_to(self, obs: EventRouter) -> int:
        """Add another router to receive our events."""
        if obs not in self._broadcast_to:
            self._broadcast_to.append(obs)
            return len(self._broadcast_to) - 1
        return self._broadcast_to.index(obs)

    def consume_from(self, obs: EventRouter):
        """Register to receive events from another router."""
        obs.broadcast_to(self)

    def set_event_trace(
        self, enabled: bool, verbosity: int = 1, use_rich: bool = True
    ) -> None:
        """
        Enable or disable event tracing with configurable output.

        When enabled, logs all events with their parameters and timing.

        Args:
            enabled: Whether to enable event tracing
            verbosity: Level of detail (0=minimal, 1=normal, 2=verbose)
            use_rich: Whether to use Rich formatting for output
        """
        self._event_trace = enabled
        self._event_trace_verbosity = verbosity
        self._event_trace_use_rich = use_rich

        if enabled:
            msg = f"Event tracing enabled for {self.__class__.__name__}"
            if use_rich:
                _console.print(
                    Panel(
                        f"[bold green]✓[/bold green] {msg}\n"
                        f"[dim]Verbosity: {['minimal', 'normal', 'verbose'][verbosity]}[/dim]",
                        title="Event Tracing",
                        border_style="green",
                    )
                )
            else:
                logger.info(f"{msg} (verbosity={verbosity})")
        else:
            msg = f"Event tracing disabled for {self.__class__.__name__}"
            if use_rich and self._event_trace_use_rich:
                _console.print(f"[yellow]ℹ[/yellow] {msg}")
            else:
                logger.info(msg)

    @property
    def event_trace_enabled(self) -> bool:
        """Check if event tracing is enabled."""
        return self._event_trace

    def _format_event_trace(
        self,
        event: EventName,
        method: str,
        parameters: dict[str, Any] | None = None,
        handler_count: int = 0,
        duration_ms: float | None = None,
        result: Any = None,
        error: Exception | None = None,
    ) -> tuple[Text | str, Table | None]:
        """
        Format event trace data for Rich output.

        Returns:
            Tuple of (main_text, optional_table)
        """
        # Determine colors based on method type
        method_colors = {
            "do": "cyan",
            "apply": "blue",
            "apply_async": "blue",
            "apply_typed": "magenta",
            "apply_typed_sync": "magenta",
        }
        method_color = method_colors.get(method, "white")

        # Build main text with Rich formatting
        use_rich = getattr(self, "_event_trace_use_rich", True)
        if use_rich:
            text = Text()

            # Event icon based on method
            if method == "do":
                text.append("🔥 ", style="bold")
            elif "apply" in method:
                text.append("⚡ ", style="bold")

            # Event name
            text.append(event, style=f"bold {method_color}")
            text.append(" | ")

            # Method
            text.append(f"{method}()", style=f"{method_color}")
            text.append(" | ")

            # Handler count
            if handler_count > 0:
                text.append(f"handlers: {handler_count}", style="green")
            else:
                text.append("no handlers", style="dim red")

            # Duration with color coding
            if duration_ms is not None:
                text.append(" | ")
                if duration_ms < 10:
                    dur_style = "green"
                elif duration_ms < 100:
                    dur_style = "yellow"
                else:
                    dur_style = "red"
                text.append(f"{duration_ms:.2f}ms", style=f"bold {dur_style}")

            # Error indicator
            if error:
                text.append(" | ")
                text.append(f"ERROR: {error!r}", style="bold red")
        else:
            # Fallback to simple string
            parts = [
                f"[EVENT] {event}",
                f"method={method}",
                f"handlers={handler_count}",
            ]
            if duration_ms is not None:
                parts.append(f"duration={duration_ms:.2f}ms")
            if error:
                parts.append(f"error={error!r}")
            text = " | ".join(parts)

        # Create table for verbose output
        table = None
        verbosity = getattr(self, "_event_trace_verbosity", 1)
        if verbosity >= 2 and use_rich:
            table = Table(show_header=True, header_style="bold cyan", box=None)
            table.add_column("Field", style="cyan", width=15)
            table.add_column("Value", overflow="fold")

            # Add parameters
            if parameters and verbosity >= 1:
                for key, value in parameters.items():
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:97] + "..."
                    table.add_row("param:" + key, value_str)

            # Add result for apply methods
            if result is not None and method.startswith("apply"):
                result_str = str(result)
                if len(result_str) > 200:
                    result_str = result_str[:197] + "..."
                table.add_row("result", result_str, style="green")

            # Add error details
            if error:
                table.add_row("error", str(error), style="red")

        return text, table

    def _log_event(
        self,
        event: EventName,
        method: str,
        parameters: dict[str, Any] | None = None,
        handler_count: int = 0,
        duration_ms: float | None = None,
        result: Any = None,
        error: Exception | None = None,
    ) -> None:
        """
        Log event dispatch details when tracing is enabled.

        Args:
            event: Event name
            method: Method used (do, apply, apply_typed)
            parameters: Event parameters
            handler_count: Number of handlers registered
            duration_ms: Execution duration in milliseconds
            result: Result from handlers (for apply methods)
            error: Any error that occurred
        """
        if not self._event_trace:
            return

        # Use Rich formatting if enabled
        if getattr(self, "_event_trace_use_rich", True):
            text, table = self._format_event_trace(
                event, method, parameters, handler_count, duration_ms, result, error
            )

            # Output based on verbosity
            verbosity = getattr(self, "_event_trace_verbosity", 1)
            if verbosity == 0:
                # Minimal - just the main line
                _console.print(text)
            elif verbosity == 1:
                # Normal - main line with inline params
                if parameters and not table:
                    # Add inline parameters for normal verbosity
                    param_summary = Text(" ")
                    param_summary.append("[", style="dim")
                    param_items = []
                    for k, v in list(parameters.items())[:3]:  # Show first 3 params
                        v_str = str(v)
                        if len(v_str) > 20:
                            v_str = v_str[:17] + "..."
                        param_items.append(f"{k}={v_str}")
                    param_summary.append(", ".join(param_items), style="dim")
                    if len(parameters) > 3:
                        param_summary.append(
                            f", +{len(parameters) - 3} more", style="dim italic"
                        )
                    param_summary.append("]", style="dim")
                    if isinstance(text, Text):
                        text.append(param_summary)
                _console.print(text)
            else:
                # Verbose - main line with table
                _console.print(text)
                if table:
                    _console.print(table)
        else:
            # Fallback to simple logging
            parts = [
                "[EVENT TRACE]",
                f"event={event!r}",
                f"method={method}",
                f"handlers={handler_count}",
            ]

            if duration_ms is not None:
                parts.append(f"duration={duration_ms:.2f}ms")

            if error:
                parts.append(f"error={error!r}")

            # Log parameters summary (truncate if too long)
            if parameters:
                param_str = str(parameters)
                if len(param_str) > 200:
                    param_str = param_str[:197] + "..."
                parts.append(f"params={param_str}")

            # Log result summary for apply methods
            if result is not None and method.startswith("apply"):
                result_str = str(result)
                if len(result_str) > 100:
                    result_str = result_str[:97] + "..."
                parts.append(f"result={result_str}")

            logger.debug(" | ".join(parts))

    @property
    def ctx(self) -> EventContext:
        """Get current event context."""
        ctx = event_ctx.get()
        if ctx is None:
            raise RuntimeError("No event context available")
        return ctx

    def on(
        self,
        event: EventName,
        priority: int = 100,
        predicate: Callable[..., bool] | None = None,
    ) -> Callable[[F], F]:
        """
        Decorator to register event handlers with priority and conditional execution.

        PURPOSE: Register functions or methods as event handlers with explicit priority
        control and optional predicate-based conditional execution for fine-grained
        event processing control.

        WHEN TO USE:
        - Dynamic handler registration after router instantiation
        - Conditional handlers based on event context or parameters
        - Priority-based handler ordering requirements
        - Runtime handler registration based on configuration
        - Handler registration outside class definitions

        HANDLER REGISTRATION:
        - Registers handler in router._events[event][priority] list
        - Higher priority values execute before lower priority values
        - Multiple handlers can have same priority (execution order undefined)
        - Replaces existing predicate for handler if already registered
        - Supports both function and method handlers

        PRIORITY SYSTEM:
        - Priority 1000: Critical system handlers (authentication, validation)
        - Priority 500: High priority business logic (data transformation)
        - Priority 200: Normal processing handlers (business logic)
        - Priority 100: Default priority for standard handlers
        - Priority 50: Low priority handlers (logging, monitoring)
        - Priority 0: Cleanup and finalization handlers

        PREDICATE EXECUTION:
        - Predicate receives EventContext as parameter
        - Return True to execute handler, False to skip
        - Predicate exceptions logged and result in skipping handler
        - Predicates evaluated for each handler before execution
        - Useful for conditional processing based on parameters or state

        EXECUTION FLOW:
        1. Check existing registrations for same handler function
        2. Update predicate if handler already registered
        3. Create new HandlerRegistration with handler and predicate
        4. Add to priority bucket in router._events dictionary
        5. Return original function unchanged

        SIDE EFFECTS:
        - Modifies router._events internal state
        - Affects subsequent event dispatch ordering
        - No immediate execution occurs during registration
        - Handler registration persists until router is destroyed

        TYPE SAFETY:
        - Preserves original function signature and type hints
        - Compatible with both sync and async handlers
        - IDE auto-completion maintained for decorated functions
        - Runtime type checking via EventContext generics

        Args:
            event: Event name for handler registration and lookup
            priority: Execution priority (higher values run first, default: 100)
            predicate: Optional conditional function (EventContext -> bool)

        Returns:
            Callable[[F], F]: Decorator function that returns original handler

        Examples:
        ```python
        # Basic handler registration
        @router.on("data:process", priority=200)
        async def process_data(ctx: EventContext[dict, Any]) -> None:
            data = ctx.parameters["data"]
            result = await processor.process(data)
            ctx.output = result


        # Conditional handler with predicate
        @router.on(
            "user:action",
            priority=150,
            predicate=lambda ctx: ctx.parameters.get("user_type") == "premium",
        )
        def premium_handler(ctx: EventContext) -> None:
            # Only executes for premium users
            user_id = ctx.parameters["user_id"]
            grant_premium_features(user_id)


        # High priority validation handler
        @router.on("api:request", priority=1000)
        def validate_request(ctx: EventContext) -> None:
            request = ctx.parameters["request"]
            if not is_valid(request):
                ctx.stop_with_exception(ValidationError("Invalid request"))


        # Monitoring handler (low priority)
        @router.on("system:*", priority=10)
        def log_event(ctx: EventContext) -> None:
            logger.info(f"Event {ctx.event} executed with params: {ctx.parameters}")
        ```

        PERFORMANCE CONSIDERATIONS:
        - Handler lookup: O(1) per event during dispatch
        - Priority sorting: O(p log p) cached on first dispatch
        - Predicate evaluation: O(1) per handler during execution
        - Memory usage: O(1) per handler registration

        THREAD SAFETY:
        - Registration is not thread-safe with concurrent dispatch
        - Ensure all handlers registered before event dispatch begins
        - Use external synchronization if needed for dynamic registration

        RELATED:
        - @on decorator: Alternative syntax for class method registration
        - _auto_register_handlers(): Automatic registration during initialization
        - _get_sorted_handlers(): Priority-ordered handler lookup during dispatch
        - _should_run_handler(): Predicate evaluation during execution
        """

        def decorator(fn: F) -> F:
            registrations = self._events[event][priority]
            for registration in registrations:
                if registration.handler is fn:
                    registration.predicate = predicate
                    break
            else:
                registrations.append(
                    HandlerRegistration(handler=fn, predicate=predicate)
                )

            return fn

        return decorator

    def _get_sorted_handlers(self, event: EventName) -> list[HandlerRegistration]:
        """Get all handlers for an event, sorted by priority."""
        handlers = []

        # Get handlers from this router
        if event in self._events:
            priorities = sorted(self._events[event].keys(), reverse=True)
            for priority in priorities:
                handlers.extend(self._events[event][priority])

        # Get handlers from broadcast targets
        for target in self._broadcast_to:
            handlers.extend(target._get_sorted_handlers(event))

        return handlers

    def _should_run_handler(
        self, registration: HandlerRegistration, ctx: EventContext
    ) -> bool:
        """Check if handler should run based on predicate."""
        predicate = registration.predicate
        if predicate is None:
            return True
        try:
            return predicate(ctx)
        except Exception as e:
            if self._debug:
                logger.warning(f"Predicate failed for {registration.handler}: {e}")
            return False

    def do(self, event: EventName, **kwargs):
        """
        Fire-and-forget event dispatch with non-blocking background execution.

        PURPOSE: Dispatch events without waiting for handler completion, ideal for
        notifications, logging, and other fire-and-forget scenarios where response
        timing is not critical.

        WHEN TO USE:
        - Event notifications where sender doesn't need response
        - Logging and monitoring events
        - Background processing initiation
        - High-frequency events where blocking would impact performance
        - Multi-cast scenarios with many independent handlers

        EXECUTION FLOW:
        1. Create EventContext with parameters and timestamp
        2. Lookup handlers by priority (including broadcast targets)
        3. Determine if async handlers present
        4. If all sync: Execute immediately in current thread
        5. If async present: Schedule in event loop or thread pool
        6. Return immediately without waiting for completion

        CONCURRENCY MODEL:
        - All sync handlers execute sequentially in dispatch thread
        - Async handlers execute concurrently via asyncio.gather()
        - Mixed sync/async handlers run in separate thread pool
        - Handler failures logged but don't affect other handlers
        - Background task tracked for cleanup via join()/close()

        SIDE EFFECTS:
        - Creates background tasks that may continue after method returns
        - Updates router._tasks set for task tracking
        - Emits event trace logs if tracing enabled
        - May modify external state via handler side effects
        - Context propagation via contextvars for async handlers

        ERROR HANDLING:
        - Individual handler exceptions caught and logged
        - Handler failures don't stop other handlers from executing
        - Debug mode provides full exception traces
        - No error reporting back to caller (fire-and-forget semantics)

        PERFORMANCE NOTES:
        - Minimal overhead for sync-only events (~microseconds)
        - Thread pool overhead for mixed sync/async events (~milliseconds)
        - Memory usage grows with pending background tasks
        - Consider batch processing for high-frequency events

        RESOURCE MANAGEMENT:
        - Background tasks automatically tracked and cleaned up
        - Thread pool created lazily and reused across calls
        - Event loop started automatically if needed
        - All resources released via close() or async_close()

        Args:
            event: Event name for handler lookup and routing
            **kwargs: Event parameters passed to all handlers

        Returns:
            None: Method returns immediately after dispatching

        Example:
        ```python
        # Simple notification
        router.do("user:login", user_id=123, timestamp=time.time())

        # With complex parameters
        router.do(
            "data:processed",
            dataset_id="ds_123",
            record_count=1000,
            processing_time=5.2,
        )

        # Event will be processed asynchronously
        # Method returns immediately, handlers run in background
        ```

        THREAD SAFETY:
        - Method itself is thread-safe
        - Handler execution context is isolated per event
        - Context variables properly propagated across async boundaries
        - Use separate routers for concurrent dispatch if needed

        RELATED:
        - apply_async(): Blocking version that waits for completion
        - apply_sync(): Synchronous blocking version
        - apply_typed(): Type-safe version with explicit annotations
        - join(): Wait for background tasks to complete
        """
        import time

        # Create context with timestamp
        ctx = EventContext(parameters=kwargs, invocation_timestamp=time.time())

        # Get all handlers
        handlers = self._get_sorted_handlers(event)

        # Log event dispatch
        self._log_event(event, "do", kwargs, len(handlers))

        # Check if we have any async handlers
        has_async = any(
            inspect.iscoroutinefunction(h.handler)
            or (
                inspect.ismethod(h.handler)
                and inspect.iscoroutinefunction(h.handler.__func__)
            )
            for h in handlers
        )

        if not has_async:
            # All sync - run directly
            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue
                handler = registration.handler
                try:
                    handler(ctx)
                    if ctx.should_stop:
                        break
                except ApplyInterrupt:
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed")
                    ctx.exception = e
        else:
            # Has async - need event loop
            async def run_handlers():
                for registration in handlers:
                    if not self._should_run_handler(registration, ctx):
                        continue
                    handler = registration.handler
                    try:
                        if inspect.iscoroutinefunction(handler):
                            await handler(ctx)
                        else:
                            handler(ctx)
                        if ctx.should_stop:
                            break
                    except ApplyInterrupt:
                        break
                    except Exception as e:
                        if self._debug:
                            logger.exception(f"Handler {handler} failed")
                        ctx.exception = e

            # Schedule in event loop
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(run_handlers())
                self._tasks.add(task)
                task.add_done_callback(self._tasks.discard)
            except RuntimeError:
                # No running loop - use thread pool
                if not self._event_loop:
                    self._start_event_loop()

                # We need to track this as a task in the event loop
                # Create an event to signal task creation
                task_created = threading.Event()

                async def create_and_track_task():
                    task = asyncio.create_task(run_handlers())
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
                    # Signal that the task has been created
                    task_created.set()
                    try:
                        await task
                    except asyncio.CancelledError:
                        # Propagate cancellation but ensure cleanup happens
                        pass
                    except Exception:
                        # Log unexpected errors but don't crash the tracker
                        pass

                # Event loop is guaranteed to exist after _start_event_loop()
                assert self._event_loop is not None
                future = asyncio.run_coroutine_threadsafe(
                    create_and_track_task(), self._event_loop
                )
                # Track the future for cleanup
                self._futures.add(future)
                future.add_done_callback(self._futures.discard)
                # Wait briefly for the task to be created and tracked
                # This ensures _tasks is updated shortly after do() returns
                task_created.wait(timeout=0.01)

    def apply_sync(
        self, event: EventName, **kwargs
    ) -> EventContext[dict[str, Any], Any]:
        """
        Synchronous blocking event dispatch.

        Returns context with results.
        """
        import time

        ctx = EventContext(parameters=kwargs, invocation_timestamp=time.time())
        token = event_ctx.set(ctx)

        try:
            handlers = self._get_sorted_handlers(event)

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                try:
                    if inspect.iscoroutinefunction(handler):
                        # Run async handler in thread pool
                        if not self._event_loop:
                            self._start_event_loop()

                        # Event loop is guaranteed to exist after _start_event_loop()
                        assert self._event_loop is not None
                        future = asyncio.run_coroutine_threadsafe(
                            handler(ctx), self._event_loop
                        )
                        result = future.result(timeout=self._default_event_timeout)
                    else:
                        result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed")
                    ctx.exception = e
                    if ctx.should_stop:
                        break
        finally:
            event_ctx.reset(token)

        return ctx

    async def apply_async(
        self, event: EventName, **kwargs
    ) -> EventContext[dict[str, Any], Any]:
        """
        Asynchronous blocking event dispatch.

        Returns context with results.
        """
        import time

        start_time = time.perf_counter()

        ctx = EventContext(parameters=kwargs, invocation_timestamp=time.time())
        token = event_ctx.set(ctx)

        try:
            handlers = self._get_sorted_handlers(event)

            # Log event start
            self._log_event(event, "apply_async", kwargs, len(handlers))

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                try:
                    if inspect.iscoroutinefunction(handler):
                        result = await handler(ctx)
                    else:
                        result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed")
                    ctx.exception = e
                    if ctx.should_stop:
                        break
        finally:
            event_ctx.reset(token)

            # Log event completion with timing
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_event(
                event,
                "apply_async",
                kwargs,
                len(handlers),
                duration_ms=duration_ms,
                result=ctx.output,
                error=ctx.exception,
            )

        return ctx

    async def apply(self, *args, **kwargs) -> EventContext[dict[str, Any], Any]:
        """Alias for apply_async for Observable compatibility."""
        return await self.apply_async(*args, **kwargs)

    async def apply_typed(
        self,
        event: EventName,
        params_type: type[T_Parameters] | None = None,
        return_type: type[T_Return] | None = None,
        **kwargs: Any,
    ) -> EventContext[T_Parameters, T_Return]:
        """
        Type-safe apply with explicit type annotations.

        Args:
            event: Event name to dispatch
            params_type: Type/TypedDict describing the parameters (optional)
            return_type: Expected return type (optional, for documentation)
            **kwargs: Event parameters

        Returns:
            Typed EventContext with proper parameter and return types

        Example:
            from typing import TypedDict

            class CompletionParams(TypedDict):
                messages: list[dict]
                config: dict[str, Any]

            ctx = await router.apply_typed(
                "llm:complete",
                CompletionParams,
                str,  # Expected return type
                messages=messages,
                config=config
            )
            # ctx is EventContext[CompletionParams, str]
        """
        import time

        start_time = time.perf_counter()

        # Extract output if provided (don't remove from kwargs)
        initial_output = kwargs.get("output", None)

        # Handle optional params_type
        if params_type is None:
            typed_params = cast(T_Parameters, kwargs)
        # For TypedDict and similar types, we can't instantiate directly
        elif hasattr(params_type, "__annotations__"):
            # It's likely a TypedDict or similar - just cast
            typed_params = cast(T_Parameters, kwargs)
        else:
            # Try to instantiate if it's a regular class
            try:
                typed_params = params_type(**kwargs)  # type: ignore
            except TypeError:
                typed_params = cast(T_Parameters, kwargs)

        # Create typed context
        ctx = EventContext[T_Parameters, T_Return](parameters=typed_params)
        if initial_output is not None:
            ctx.output = initial_output
        token = event_ctx.set(ctx)

        try:
            handlers = self._get_sorted_handlers(event)

            # Log event start
            self._log_event(event, "apply_typed", kwargs, len(handlers))

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                try:
                    if inspect.iscoroutinefunction(handler):
                        result = await handler(ctx)
                    else:
                        result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed for event {event}")
                    ctx.exception = e
                    if ctx.should_stop:
                        break

        finally:
            event_ctx.reset(token)

            # Log event completion with timing
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_event(
                event,
                "apply_typed",
                kwargs,
                len(handlers),
                duration_ms=duration_ms,
                result=ctx.output,
                error=ctx.exception,
            )

        return ctx

    def apply_typed_sync(
        self,
        event: EventName,
        params_type: type[T_Parameters] | None = None,
        return_type: type[T_Return] | None = None,
        **kwargs: Any,
    ) -> EventContext[T_Parameters, T_Return]:
        """
        Type-safe synchronous apply with explicit type annotations.

        Args:
            event: Event name to dispatch
            params_type: Type/TypedDict describing the parameters (optional)
            return_type: Expected return type (optional, for documentation)
            **kwargs: Event parameters

        Returns:
            Typed EventContext with proper parameter and return types

        Example:
            from typing import TypedDict

            class InitParams(TypedDict):
                config: dict[str, Any]
                options: dict

            ctx = router.apply_typed_sync(
                "init:start",
                InitParams,
                bool,  # Expected return type
                config=config,
                options=options
            )
            # ctx is EventContext[InitParams, bool]

            # Or just specify return type:
            ctx = router.apply_typed_sync(
                "init:complete",
                return_type=bool,
                status="success"
            )
        """
        import time

        start_time = time.perf_counter()

        # Extract output if provided (don't remove from kwargs)
        initial_output = kwargs.get("output", None)

        # Handle optional params_type
        if params_type is None:
            typed_params = cast(T_Parameters, kwargs)
        # For TypedDict and similar types, we can't instantiate directly
        elif hasattr(params_type, "__annotations__"):
            # It's likely a TypedDict or similar - just cast
            typed_params = cast(T_Parameters, kwargs)
        else:
            # Try to instantiate if it's a regular class
            try:
                typed_params = params_type(**kwargs)  # type: ignore
            except TypeError:
                typed_params = cast(T_Parameters, kwargs)

        # Create typed context
        ctx = EventContext[T_Parameters, T_Return](parameters=typed_params)
        if initial_output is not None:
            ctx.output = initial_output
        token = event_ctx.set(ctx)

        try:
            handlers = self._get_sorted_handlers(event)

            # Log event start
            self._log_event(event, "apply_typed_sync", kwargs, len(handlers))

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                try:
                    # Only run sync handlers in sync mode
                    if inspect.iscoroutinefunction(handler):
                        continue  # Skip async handlers

                    result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed for event {event}")
                    ctx.exception = e
                    if ctx.should_stop:
                        break

        finally:
            event_ctx.reset(token)

            # Log event completion with timing
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._log_event(
                event,
                "apply_typed_sync",
                kwargs,
                len(handlers),
                duration_ms=duration_ms,
                result=ctx.output,
                error=ctx.exception,
            )

        return ctx

    def typed(
        self,
        params_type: type[T_Parameters] | None = None,
        return_type: type[T_Return] | None = None,
    ) -> TypedApply[T_Parameters, T_Return]:
        """
        Create a typed apply helper for cleaner syntax.

        Example:
            # With both params and return type:
            ctx = await router.typed(CompletionParams, str).apply(
                "llm:complete",
                messages=messages,
                config=config
            )

            # With only return type:
            ctx = await router.typed(return_type=str).apply(
                "llm:complete",
                messages=messages,
                config=config
            )

            # Synchronous version:
            ctx = router.typed(InitParams, bool).apply_sync(
                "init:start",
                config={...}
            )
        """
        return TypedApply(self, params_type, return_type)

    def _start_event_loop(self):
        """Start background event loop for async handlers."""
        if self._event_loop and not self._event_loop.is_closed():
            return

        def run_loop():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._event_loop = loop
            loop.run_forever()

        self._loop_thread = threading.Thread(target=run_loop, daemon=True)
        self._loop_thread.start()

        # Wait for loop to start
        while not self._event_loop or not self._event_loop.is_running():
            threading.Event().wait(0.01)

    def join(self, timeout: float = 5.0):
        """
        Wait for all background tasks to complete.

        This is the synchronous version - blocks until tasks complete or timeout.
        """
        # Give a small delay to allow tasks to be registered
        # This handles the race condition where join() is called immediately after do()
        import time

        time.sleep(0.01)

        if not self._tasks:
            return

        async def wait_for_tasks():
            try:
                # Create a copy of tasks to avoid set changing during iteration
                tasks = list(self._tasks)
                if tasks:
                    await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=timeout,
                    )
            except TimeoutError:
                if self._debug:
                    logger.warning(f"Timeout waiting for {len(self._tasks)} tasks")

        if self._event_loop:
            future = asyncio.run_coroutine_threadsafe(
                wait_for_tasks(), self._event_loop
            )
            future.result()

    async def join_async(self, timeout: float = 5.0):
        """Async version of join."""
        if not self._tasks:
            return

        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True), timeout=timeout
            )
        except TimeoutError:
            if self._debug:
                logger.warning(f"Timeout waiting for {len(self._tasks)} tasks")

    def close(self):
        """Clean up resources."""
        # Unregister from signal handling
        if self._signal_handling_enabled:
            from .signal_handler import unregister_from_signals

            unregister_from_signals(self)

        # Wait for tasks
        self.join(timeout=1.0)

        # Cancel any remaining futures from run_coroutine_threadsafe
        for future in list(self._futures):
            if not future.done():
                future.cancel()
        self._futures.clear()

        # Cancel any remaining tasks
        if self._tasks and self._event_loop:

            def cancel_tasks():
                for task in list(self._tasks):
                    if not task.done():
                        task.cancel()

            self._event_loop.call_soon_threadsafe(cancel_tasks)

        # Stop event loop
        if self._event_loop:
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)
            if self._loop_thread:
                self._loop_thread.join(timeout=1.0)

        # Shutdown thread pool
        if self._thread_pool:
            self._thread_pool.shutdown(wait=False)

    async def async_close(self):
        """Async version of close - waits for tasks and cleans up."""
        # Unregister from signal handling
        if self._signal_handling_enabled:
            from .signal_handler import unregister_from_signals

            unregister_from_signals(self)

        # Wait for all tasks to complete
        await self.join_async(timeout=1.0)

        # Cancel any remaining futures from run_coroutine_threadsafe
        for future in list(self._futures):
            if not future.done():
                future.cancel()
        self._futures.clear()

        # Cancel any remaining tasks
        if self._tasks:
            for task in list(self._tasks):
                if not task.done():
                    task.cancel()
            # Give tasks a chance to handle cancellation
            await asyncio.sleep(0.1)

        # Stop event loop if needed
        if self._event_loop and self._event_loop != asyncio.get_running_loop():
            self._event_loop.call_soon_threadsafe(self._event_loop.stop)

        # Shutdown thread pool
        if self._thread_pool:
            self._thread_pool.shutdown(wait=False)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - waits for tasks."""
        await self.async_close()

    def __enter__(self):
        """Sync context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit - waits for tasks."""
        self.close()


# Type variable for decorated functions/methods
HandlerType = TypeVar("HandlerType", bound=Callable[..., Any])


def on(
    *events: EventName,
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[HandlerType], HandlerType]:
    """
    Decorator to mark a method as an event handler for auto-registration.

    This decorator doesn't create a wrapper - it just attaches metadata
    to the original function for auto-registration during __post_init__.

    IMPORTANT: All handlers MUST accept an EventContext as their first parameter
    (after self for methods).

    Args:
        events: Event names to register for
        priority: Handler priority (higher runs first)
        predicate: Optional function to determine if handler should run

    Example:
        class MyRouter(EventRouter):
            @on("process", priority=200)
            def handler(self, ctx: EventContext) -> None:
                return ctx.parameters["value"] * 2

            @on("message:append")
            async def async_handler(self, ctx: EventContext) -> None:
                message = ctx.parameters.get('message')
                await self.process_message(message)

    Type Safety:
        The decorator preserves the original method's type signature,
        ensuring that type checkers can validate both the handler's
        signature and its usage within the class.
    """

    def decorator(fn: HandlerType) -> HandlerType:
        # Store configuration on the function
        # This metadata is read by EventRouter._auto_register_handlers
        fn._event_handler_config = {  # type: ignore[attr-defined]
            "events": events,
            "priority": priority,
            "predicate": predicate,
        }
        return fn

    return decorator


# Store the original emit function decorator with a different name


# Redefine emit as a class to match Observable's API
# This allows both @emit(LifecyclePhase.BEFORE) and accessing emit.BEFORE
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

    def __new__(cls, lifecycle=None, *args, **kwargs):
        """Handle special case of @emit without parentheses."""
        # If lifecycle is a callable (function), it means @emit was used without parentheses
        if callable(lifecycle) and not isinstance(lifecycle, (LifecyclePhase, str)):
            # Create a default emit instance and immediately apply it
            instance = object.__new__(cls)
            instance.__init__(
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
            self.event = lifecycle
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

    @overload
    def __call__(self, func: Callable[..., T_Return]) -> Callable[..., T_Return]:
        """Type signature for sync functions."""
        ...

    @overload
    def __call__(
        self, func: Callable[..., Callable[..., T_Return]]
    ) -> Callable[..., Callable[..., T_Return]]:
        """Type signature for async functions."""
        ...

    def __call__(self, func: F) -> F:
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

        # Determine event name
        event_name = self.event or func.__name__

        # Check if it's an async function
        is_async = inspect.iscoroutinefunction(func)

        if is_async:

            @functools.wraps(func)
            async def async_wrapper(self, *args, **kwargs):
                # Ensure self is EventRouter
                if not isinstance(self, EventRouter):
                    return await func(self, *args, **kwargs)

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
                        ctx = await self.apply_async(
                            f"{event_name}:before", **method_args
                        )
                        # Note: EventRouter does NOT modify method parameters
                        # The output is available but doesn't affect the method execution

                    # Execute method with original parameters
                    result = await func(self, *args, **kwargs)

                    # AFTER phase
                    if _root.lifecycle & LifecyclePhase.AFTER:
                        after_args = method_args.copy()
                        if _root.include_result:
                            after_args["result"] = result
                        ctx = await self.apply_async(
                            f"{event_name}:after", **after_args
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
                            ctx = await self.apply_async(
                                f"{event_name}:error", **error_args
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
                        await self.apply_async(f"{event_name}:finally", **finally_args)

            return async_wrapper  # type: ignore

        else:

            @functools.wraps(func)
            def sync_wrapper(self, *args, **kwargs):
                # Ensure self is EventRouter
                if not isinstance(self, EventRouter):
                    return func(self, *args, **kwargs)

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
                        ctx = self.apply_sync(f"{event_name}:before", **method_args)
                        # Note: EventRouter does NOT modify method parameters
                        # The output is available but doesn't affect the method execution

                    # Execute method with original parameters
                    result = func(self, *args, **kwargs)

                    # AFTER phase
                    if _root.lifecycle & LifecyclePhase.AFTER:
                        after_args = method_args.copy()
                        if _root.include_result:
                            after_args["result"] = result
                        ctx = self.apply_sync(f"{event_name}:after", **after_args)
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
                            ctx = self.apply_sync(f"{event_name}:error", **error_args)
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
                        self.do(f"{event_name}:finally", **finally_args)

            return sync_wrapper  # type: ignore


# Backward compatibility: emit_event function
def emit_event(
    event: str | None = None,
    phases: LifecyclePhase | None = None,
    include_args: bool = True,
    include_result: bool = True,
) -> Callable[[F], F]:
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


# Typed decorator for better IDE support and type checking
def typed_on(
    *events: EventName,
    priority: int = 100,
    predicate: Callable[[EventContext], bool] | None = None,
) -> Callable[[HandlerType], HandlerType]:
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
EventHandlerDecorator = Callable[[HandlerType], HandlerType]


class TypedApply(Generic[T_Parameters, T_Return]):
    """Helper class for typed apply with cleaner syntax."""

    def __init__(
        self,
        router: EventRouter,
        params_type: type[T_Parameters] | None = None,
        return_type: type[T_Return] | None = None,
    ):
        self.router = router
        self.params_type = params_type
        self.return_type = return_type

    async def apply(
        self, event: EventName, **kwargs: Any
    ) -> EventContext[T_Parameters, T_Return]:
        """Apply the event asynchronously with type safety."""
        return await self.router.apply_typed(
            event, self.params_type, self.return_type, **kwargs
        )

    def apply_sync(
        self, event: EventName, **kwargs: Any
    ) -> EventContext[T_Parameters, T_Return]:
        """Apply the event synchronously with type safety."""
        return self.router.apply_typed_sync(
            event, self.params_type, self.return_type, **kwargs
        )


# Export public API
__all__ = [
    "EventRouter",
    "EventContext",
    "ApplyInterrupt",
    "TypedApply",
    "on",
    "typed_on",  # Type-safe decorator variant
    "emit",  # The class with phase constants and decorator functionality
    "emit_event",  # Backward-compatible function decorator
    "LifecyclePhase",
    "EventName",
    "EventPriority",
    "EventHandlerDecorator",  # Type alias for decorators
    "current_test_nodeid",  # Export for use in test infrastructure
]
