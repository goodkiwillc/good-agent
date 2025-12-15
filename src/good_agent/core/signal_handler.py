import asyncio
import logging
import signal
import sys
import threading
import weakref
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class _RouterRef:
    """Weak-ref friendly wrapper that falls back to strong references when needed."""

    __slots__ = ("_weakref", "_strong", "_hash")

    def __init__(self, router: Any, finalizer: Callable[[_RouterRef], None]):
        self._hash = id(router)
        self._weakref: weakref.ref[Any] | None = None
        self._strong: Any | None = None

        def _cleanup(_: weakref.ref[Any]) -> None:
            finalizer(self)

        try:
            self._weakref = weakref.ref(router, _cleanup)
        except TypeError:
            self._strong = router

    def __call__(self) -> Any | None:
        if self._weakref is not None:
            return self._weakref()
        return self._strong

    def __hash__(self) -> int:
        return self._hash

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _RouterRef):
            return self() is other()
        return False


class SignalHandler:
    """
    Manages signal handling for graceful shutdown of async tasks.

    This class intercepts SIGINT/SIGTERM signals and ensures that:
    1. All tracked async tasks are cancelled
    2. Event loops are properly shut down
    3. Resources are cleaned up gracefully
    """

    def __init__(self):
        """Initialize the signal handler."""
        self._original_handlers: dict[int, Any] = {}
        self._registered_routers: set[_RouterRef] = set()
        self._shutdown_initiated = False
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()

    def register_router(self, router: Any) -> None:
        """
        Register an EventRouter instance for signal handling.

        Args:
            router: EventRouter instance to track
        """
        with self._lock:
            # Use weak reference to avoid keeping routers alive
            self._registered_routers.add(_RouterRef(router, self._on_router_deleted))

            # Install signal handlers on first registration
            if len(self._registered_routers) == 1:
                self._install_handlers()

    def unregister_router(self, router: Any) -> None:
        """
        Unregister an EventRouter instance.

        Args:
            router: EventRouter instance to stop tracking
        """
        with self._lock:
            # Find and remove the weak reference
            to_remove = None
            for ref in self._registered_routers:
                if ref() is router:
                    to_remove = ref
                    break

            if to_remove:
                self._registered_routers.discard(to_remove)

            # Remove signal handlers if no more routers
            if not self._registered_routers:
                self._restore_handlers()

    def _on_router_deleted(self, ref: _RouterRef) -> None:
        """Called when a router is garbage collected."""
        with self._lock:
            self._registered_routers.discard(ref)

            # Remove signal handlers if no more routers
            if not self._registered_routers:
                self._restore_handlers()

    def _install_handlers(self) -> None:
        """Install signal handlers for SIGINT and SIGTERM."""
        if sys.platform != "win32":
            # Unix-like systems
            self._original_handlers[signal.SIGINT] = signal.signal(
                signal.SIGINT, self._handle_signal
            )
            self._original_handlers[signal.SIGTERM] = signal.signal(
                signal.SIGTERM, self._handle_signal
            )
        else:
            # Windows only supports SIGINT
            self._original_handlers[signal.SIGINT] = signal.signal(
                signal.SIGINT, self._handle_signal
            )

    def _restore_handlers(self) -> None:
        """Restore original signal handlers."""
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)
        self._original_handlers.clear()

    def _handle_signal(self, signum: int, frame: Any) -> None:
        """
        Handle incoming signals.

        This method is called from the signal handler context and must be
        thread-safe and re-entrant safe.
        """
        # Prevent multiple signal handling
        with self._lock:
            if self._shutdown_initiated:
                # Force exit on second signal
                logger.warning("Forced shutdown requested")
                sys.exit(1)

            self._shutdown_initiated = True
            signal_name = signal.Signals(signum).name
            logger.info(f"Received {signal_name}, initiating graceful shutdown...")

        # Cancel all tasks in all registered routers
        self._cancel_all_tasks()

        # Set shutdown event
        self._shutdown_event.set()

        # Call original handler if it's callable (not SIG_DFL or SIG_IGN)
        original = self._original_handlers.get(signum)
        if callable(original):
            try:
                # Check if this is an asyncio.Runner handler that needs special handling
                if (
                    hasattr(original, "func")
                    and hasattr(original.func, "__qualname__")
                    and "Runner._on_sigint" in original.func.__qualname__
                ):
                    # asyncio.Runner handler - don't call from signal context
                    # Instead just raise KeyboardInterrupt which is what it would do
                    logger.debug("Detected asyncio.Runner handler, raising KeyboardInterrupt")
                    raise KeyboardInterrupt()
                else:
                    # Safe to call other handlers
                    original(signum, frame)
            except Exception as e:
                # If original handler fails, log and continue with KeyboardInterrupt
                logger.warning(f"Original signal handler failed: {e}")
                if signum == signal.SIGINT:
                    raise KeyboardInterrupt() from e
        elif original == signal.default_int_handler:
            # Raise KeyboardInterrupt for SIGINT
            raise KeyboardInterrupt()

    def _cancel_all_tasks(self) -> None:
        """Cancel all tasks in all registered routers."""
        cancelled_count = 0
        router_count = 0

        with self._lock:
            for ref in list(self._registered_routers):
                router = ref()
                if router is None:
                    continue

                router_count += 1

                # Cancel all tasks in the router
                if hasattr(router, "_tasks"):
                    for task in list(router._tasks):
                        if not task.done():
                            task.cancel()
                            cancelled_count += 1

                # Also cancel agent-managed tasks if present (Agent extends EventRouter)
                tasks_attr = None
                task_manager = getattr(router, "tasks", None)
                if task_manager is not None:
                    managed = getattr(task_manager, "managed_tasks", None)
                    if managed is not None:
                        tasks_attr = list(managed.keys())
                elif hasattr(router, "_managed_tasks"):
                    try:
                        tasks_attr = list(router._managed_tasks.keys())
                    except Exception:  # pragma: no cover - defensive
                        tasks_attr = None

                if tasks_attr:
                    for task in tasks_attr:
                        if not task.done():
                            task.cancel()
                            cancelled_count += 1

                # Stop event loop if running in thread
                if hasattr(router, "_event_loop") and router._event_loop:
                    loop = router._event_loop
                    if loop.is_running():
                        loop.call_soon_threadsafe(loop.stop)

        if cancelled_count > 0:
            logger.info(f"Cancelled {cancelled_count} tasks in {router_count} routers")

    def is_shutdown_initiated(self) -> bool:
        """Check if shutdown has been initiated."""
        return self._shutdown_initiated

    def wait_for_shutdown(self, timeout: float | None = None) -> bool:
        """
        Wait for shutdown signal.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if shutdown was initiated, False if timeout
        """
        return self._shutdown_event.wait(timeout)

    async def wait_for_shutdown_async(self) -> None:
        """Async version of wait_for_shutdown."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._shutdown_event.wait)


# Global signal handler instance
_global_handler = SignalHandler()


def register_for_signals(router: Any) -> None:
    """
    Register an EventRouter for signal handling.

    Args:
        router: EventRouter instance to register
    """
    _global_handler.register_router(router)


def unregister_from_signals(router: Any) -> None:
    """
    Unregister an EventRouter from signal handling.

    Args:
        router: EventRouter instance to unregister
    """
    _global_handler.unregister_router(router)


def is_shutdown_requested() -> bool:
    """Check if a shutdown signal has been received."""
    return _global_handler.is_shutdown_initiated()


async def wait_for_shutdown() -> None:
    """Wait for a shutdown signal asynchronously."""
    await _global_handler.wait_for_shutdown_async()


class GracefulShutdownMixin:
    """
    Mixin class that adds graceful shutdown capabilities to EventRouter.

    Usage:
        class MyRouter(GracefulShutdownMixin, EventRouter):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.enable_signal_handling()
    """

    def enable_signal_handling(self) -> None:
        """Enable signal handling for this router."""
        register_for_signals(self)

    def disable_signal_handling(self) -> None:
        """Disable signal handling for this router."""
        unregister_from_signals(self)

    async def shutdown_gracefully(self, timeout: float = 5.0) -> None:
        """
        Perform graceful shutdown.

        Args:
            timeout: Maximum time to wait for tasks to complete
        """
        # Cancel all tasks
        if hasattr(self, "_tasks"):
            for task in list(self._tasks):
                if not task.done():
                    task.cancel()

        # Wait for tasks to complete
        join_coro: Any = None
        if hasattr(self, "join"):
            join_coro = self.join()
        elif hasattr(self, "join_async"):
            join_coro = self.join_async()

        if join_coro is not None:
            try:
                await asyncio.wait_for(join_coro, timeout=timeout)
            except TimeoutError:
                logger.warning(f"Timeout waiting for tasks after {timeout}s")

        # Close the router
        if hasattr(self, "close"):
            await self.close()
        elif hasattr(self, "async_close"):
            await self.async_close()

    def __del__(self):
        """Ensure we unregister on deletion."""
        try:
            self.disable_signal_handling()
        except Exception:
            pass  # Ignore errors during cleanup
