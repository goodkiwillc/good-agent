"""Priority-based EventRouter with thread-safe registration and sync/async bridging."""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from collections.abc import Callable
from typing import Any, cast

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from good_agent.core.event_router.context import EventContext, event_ctx
from good_agent.core.event_router.protocols import (
    ApplyInterrupt,
    EventName,
    F,
    T_Parameters,
    T_Return,
)
from good_agent.core.event_router.registration import (
    HandlerRegistration,
    HandlerRegistry,
)
from good_agent.core.event_router.sync_bridge import SyncBridge

logger = logging.getLogger(__name__)

# Create a console instance for Rich output
_console = Console(stderr=True)  # Use stderr to avoid interfering with stdout


class EventRouter:
    """Priority-aware dispatcher powering agents, components, and extensions.

    Supports predicates, lifecycle hooks, broadcast chaining, and the
    sync/async bridge showcased in ``examples/event_router/*.py``.
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

        # Handler registry (thread-safe)
        self._handler_registry = HandlerRegistry(debug=debug)

        # Maintain broadcast targets for backward compatibility
        self._broadcast_to: list[EventRouter] = []

        # Async/sync bridge for task tracking and event loop management
        self._sync_bridge = SyncBridge(debug=debug, default_timeout=default_event_timeout)

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
            from good_agent.core.signal_handler import register_for_signals

            register_for_signals(self)

    def _link_broadcast_target(self, obs: EventRouter, *, bidirectional: bool) -> int:
        """Internal helper to register broadcast targets with optional reciprocity."""

        if obs not in self._broadcast_to:
            self._broadcast_to.append(obs)
            index = len(self._broadcast_to) - 1
        else:
            index = self._broadcast_to.index(obs)

        self._handler_registry.add_broadcast_target(obs._handler_registry)

        if bidirectional:
            obs._link_broadcast_target(self, bidirectional=False)

        return index

    def broadcast_to(self, obs: EventRouter) -> int:
        """Add another router to receive our events (bidirectionally)."""

        return self._link_broadcast_target(obs, bidirectional=True)

    def consume_from(self, obs: EventRouter):
        """Register to receive events from another router."""
        obs._link_broadcast_target(self, bidirectional=False)

    def set_event_trace(self, enabled: bool, verbosity: int = 1, use_rich: bool = True) -> None:
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
        error: BaseException | None = None,
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
        text: Text | str
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
        error: BaseException | None = None,
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
                        param_summary.append(f", +{len(parameters) - 3} more", style="dim italic")
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

    def _wrap_handler_for_registration(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Wrap callables that do not expose a writable __dict__."""

        bound_self = getattr(fn, "__self__", None)
        target = getattr(fn, "__func__", None) or fn
        is_async = inspect.iscoroutinefunction(target)

        def invoke(*args, **kwargs):
            if bound_self is None:
                return target(*args, **kwargs)
            return target(bound_self, *args, **kwargs)

        if is_async:

            @functools.wraps(target)
            async def async_wrapper(*args, **kwargs):
                return await invoke(*args, **kwargs)

            return async_wrapper

        @functools.wraps(target)
        def sync_wrapper(*args, **kwargs):
            return invoke(*args, **kwargs)

        return sync_wrapper

    @staticmethod
    def _supports_metadata_assignment(fn: Callable[..., Any]) -> bool:
        """Check if we can attach attributes to the handler."""

        sentinel = "__event_router_handler_probe__"
        if hasattr(fn, sentinel):
            return True
        try:
            setattr(fn, sentinel, True)
            delattr(fn, sentinel)
            return True
        except (AttributeError, TypeError):
            return False

    def on(
        self,
        event: EventName,
        priority: int = 100,
        predicate: Callable[..., bool] | None = None,
    ) -> Callable[[F], F]:
        """Register a handler for ``event`` with optional priority and predicate.

        The handler ID is attached to the returned function as `_handler_id` attribute,
        which can be used with `deregister()` to remove the handler.

        See ``examples/event_router/basic_usage.py`` for typical patterns.
        """

        def decorator(fn: F) -> F:
            handler_callable: Callable[..., Any]
            attr_target: Callable[..., Any]

            if self._supports_metadata_assignment(fn):
                handler_callable = fn  # type: ignore[assignment]
                attr_target = fn  # type: ignore[assignment]
            else:
                handler_callable = self._wrap_handler_for_registration(fn)
                attr_target = handler_callable

            handler_id = self._handler_registry.register_handler(
                event=event,
                handler=handler_callable,
                priority=priority,
                predicate=predicate,
            )
            # Attach handler ID to function for later deregistration
            attr_target._handler_id = handler_id  # type: ignore[attr-defined]
            return cast(F, attr_target)

        return decorator

    def _get_sorted_handlers(self, event: EventName) -> list[HandlerRegistration]:
        """Return handlers ordered by priority (includes broadcast targets)."""
        return self._handler_registry.get_sorted_handlers(event)

    def _should_run_handler(self, registration: HandlerRegistration, ctx: EventContext) -> bool:
        """Check if handler should run based on predicate result."""
        return self._handler_registry.should_run_handler(registration, ctx)

    def _build_typed_parameters(
        self,
        params_type: type[T_Parameters] | None,
        kwargs: dict[str, Any],
    ) -> T_Parameters:
        """Instantiate typed parameters when possible, falling back to raw kwargs."""

        if params_type is None:
            return cast(T_Parameters, kwargs)

        try:
            return cast(T_Parameters, params_type(**kwargs))  # type: ignore[arg-type]
        except Exception:
            return cast(T_Parameters, kwargs)

    def _is_async_handler(self, handler: Callable[..., Any]) -> bool:
        """Detect coroutine functions, including bound methods."""

        return inspect.iscoroutinefunction(handler) or (
            inspect.ismethod(handler) and inspect.iscoroutinefunction(handler.__func__)  # type: ignore[attr-defined]
        )

    def do(self, event: EventName, **kwargs):
        """Dispatch event handlers without waiting for completion."""

        # Create context with timestamp
        ctx: EventContext = EventContext(parameters=kwargs, invocation_timestamp=time.time())
        ctx.event = event

        # Get all handlers
        handlers = self._get_sorted_handlers(event)

        # Log event dispatch
        self._log_event(event, "do", kwargs, len(handlers))

        # Check if we have any async handlers
        has_async = any(self._is_async_handler(h.handler) for h in handlers)

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

            async def run_handlers():
                for registration in handlers:
                    if not self._should_run_handler(registration, ctx):
                        continue
                    handler = registration.handler
                    is_async_handler = self._is_async_handler(handler)
                    try:
                        if is_async_handler:
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

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                task = loop.create_task(run_handlers())
                self._sync_bridge.track_task(task)
            else:
                self._sync_bridge.create_background_task(run_handlers())

    def apply_sync(self, event: EventName, **kwargs) -> EventContext[dict[str, Any], Any]:
        """
        Synchronous blocking event dispatch.

        Returns context with results.

        Raises:
            RuntimeError: If called from within the event loop thread (nested
                sync call from async handler would cause deadlock)
        """
        # Prevent deadlock: detect if we're being called from within an async
        # handler running on the event loop thread
        if self._sync_bridge.is_event_loop_thread:
            raise RuntimeError(
                "Cannot call apply_sync() from within an async event handler "
                "running on the event loop thread. This would cause a deadlock. "
                "Use 'await router.apply_async()' instead for nested event dispatch."
            )

        ctx: EventContext[dict[str, Any], Any] = EventContext(
            parameters=kwargs, invocation_timestamp=time.time()
        )
        ctx.event = event
        token = event_ctx.set(ctx)
        sync_exception_to_raise: BaseException | None = None

        try:
            handlers = self._get_sorted_handlers(event)

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                is_async_handler = self._is_async_handler(handler)
                try:
                    if is_async_handler:
                        result = self._sync_bridge.run_coroutine_from_sync(
                            handler(ctx), timeout=self._default_event_timeout
                        )
                    else:
                        result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    if is_async_handler and not ctx.should_stop:
                        raise
                    break
                except RuntimeError as e:
                    # Re-raise RuntimeErrors that indicate programming errors
                    # (e.g., nested apply_sync deadlock)
                    if "Cannot call apply_sync()" in str(e):
                        raise
                    # Store other RuntimeErrors
                    if self._debug:
                        logger.exception(f"Handler {handler} failed")
                    ctx.exception = e
                    if not is_async_handler and sync_exception_to_raise is None:
                        sync_exception_to_raise = e
                    if ctx.should_stop:
                        break
                    continue
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed")
                    ctx.exception = e
                    if not is_async_handler and sync_exception_to_raise is None:
                        sync_exception_to_raise = e
                    if ctx.should_stop:
                        break
                    continue
        finally:
            event_ctx.reset(token)

        if (
            sync_exception_to_raise is not None
            and not ctx.stopped_with_exception
            and not isinstance(sync_exception_to_raise, ApplyInterrupt)
        ):
            raise sync_exception_to_raise

        return ctx

    async def apply_async(self, event: EventName, **kwargs) -> EventContext[dict[str, Any], Any]:
        """
        Asynchronous blocking event dispatch.

        Returns context with results.
        """

        start_time = time.perf_counter()

        ctx: EventContext[dict[str, Any], Any] = EventContext(
            parameters=kwargs, invocation_timestamp=time.time()
        )
        ctx.event = event
        token = event_ctx.set(ctx)

        try:
            handlers = self._get_sorted_handlers(event)

            # Log event start
            self._log_event(event, "apply_async", kwargs, len(handlers))

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                is_async_handler = self._is_async_handler(handler)
                try:
                    if is_async_handler:
                        result = await handler(ctx)
                    else:
                        result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    if is_async_handler and not ctx.should_stop:
                        raise
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed")
                    ctx.exception = e
                    if ctx.should_stop:
                        break
                    continue
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
        """Type-safe variant of ``apply_async``.

        Use when you want IDE/type-checker awareness of the event payload. See
        ``examples/event_router/basic_usage.py`` for a complete sample.
        """

        start_time = time.perf_counter()

        # Extract output if provided (don't remove from kwargs)
        initial_output = kwargs.get("output")

        typed_params = self._build_typed_parameters(params_type, kwargs)

        # Create typed context
        ctx = EventContext[T_Parameters, T_Return](parameters=typed_params)
        if initial_output is not None:
            ctx.output = initial_output
        ctx.event = event
        token = event_ctx.set(ctx)

        try:
            handlers = self._get_sorted_handlers(event)

            # Log event start
            self._log_event(event, "apply_typed", kwargs, len(handlers))

            for registration in handlers:
                if not self._should_run_handler(registration, ctx):
                    continue

                handler = registration.handler
                is_async_handler = self._is_async_handler(handler)
                try:
                    if is_async_handler:
                        result = await handler(ctx)
                    else:
                        result = handler(ctx)

                    if result is not None:
                        ctx.output = result

                    if ctx.should_stop:
                        break

                except ApplyInterrupt:
                    if is_async_handler and not ctx.should_stop:
                        raise
                    break
                except Exception as e:
                    if self._debug:
                        logger.exception(f"Handler {handler} failed for event {event}")
                    ctx.exception = e
                    if ctx.should_stop:
                        break
                    continue

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
        """Synchronous counterpart to ``apply_typed``."""

        start_time = time.perf_counter()

        # Extract output if provided (don't remove from kwargs)
        initial_output = kwargs.get("output")

        typed_params = self._build_typed_parameters(params_type, kwargs)

        # Create typed context
        ctx = EventContext[T_Parameters, T_Return](parameters=typed_params)
        if initial_output is not None:
            ctx.output = initial_output
        ctx.event = event
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
                    if self._is_async_handler(handler):
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
    ):
        """Helper returning a fluent API wrapper for typed apply calls."""
        # Import here to avoid circular dependency
        from good_agent.core.event_router.advanced import TypedApply  # type: ignore[attr-defined]

        return TypedApply(self, params_type, return_type)

    async def join(self, timeout: float = 5.0) -> None:
        """Wait for all background tasks to complete."""
        await self._sync_bridge.join(timeout=timeout)

    def join_sync(self, timeout: float = 5.0) -> None:
        """Synchronous helper that blocks until all background tasks complete."""
        self._sync_bridge.join_sync(timeout=timeout)

    async def close(self) -> None:
        """Clean up resources and wait for outstanding tasks."""
        # Unregister from signal handling
        if self._signal_handling_enabled:
            from good_agent.core.signal_handler import unregister_from_signals

            unregister_from_signals(self)
        await self._sync_bridge.close()

    def close_sync(self) -> None:
        """Synchronous helper that performs immediate cleanup."""
        if self._signal_handling_enabled:
            from good_agent.core.signal_handler import unregister_from_signals

            unregister_from_signals(self)

        self._sync_bridge.close_sync()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - waits for tasks."""
        await self.close()

    def __enter__(self):
        """Sync context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit - waits for tasks."""
        self.close_sync()

    @property
    def _events(self):
        """Backward-compatible view of handler registrations (read-only)."""
        return self._handler_registry._events
