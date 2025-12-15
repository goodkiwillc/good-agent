"""Handler registration and management with thread-safe access.

This module contains the handler registration system for the event router,
including the registry data structure, handler lookup, and thread-safe
registration operations.

CONTENTS:
- HandlerRegistration: Metadata for registered handlers
- LifecyclePhase: Enum for method lifecycle phases (@emit decorator)
- HandlerRegistry: Thread-safe handler storage and lookup
- current_test_nodeid: Context variable for pytest integration

THREAD SAFETY: All handler registration operations are protected by threading.RLock
to ensure safe concurrent access during registration and dispatch.
"""

from __future__ import annotations

import collections
import contextvars
import enum
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from good_agent.core.event_router.context import EventContext
    from good_agent.core.event_router.protocols import EventName, EventPriority

logger = logging.getLogger(__name__)


@dataclass
class HandlerRegistration:
    """Registration metadata for an event handler.

    This dataclass stores the handler function/method along with optional
    predicate for conditional execution.

    Attributes:
        handler: The callable handler function or method
        predicate: Optional condition function that determines if handler should execute
    """

    handler: Callable[..., Any]
    """The handler function or method to execute."""

    predicate: Callable[[EventContext], bool] | None = None
    """Optional predicate function for conditional execution."""


class LifecyclePhase(enum.Flag):
    """Phases in method lifecycle for @emit decorator.

    Uses enum.Flag to allow bitwise operations like Observable's Lifecycle:
        phases = LifecyclePhase.BEFORE | LifecyclePhase.AFTER

    Lifecycle phases allow handlers to be triggered at different points
    during method execution:
    - BEFORE: Before method body executes
    - AFTER: After successful method execution
    - ERROR: After method raises an exception
    - FINALLY: Always executes after method (success or failure)

    Example:
        ```python
        @emit("user:login", phases=LifecyclePhase.BEFORE | LifecyclePhase.AFTER)
        async def login(self, username: str) -> User:
            # Emits "user:login:before" event
            user = await authenticate(username)
            # Emits "user:login:after" event
            return user
        ```
    """

    BEFORE = enum.auto()
    """Execute before method body."""

    AFTER = enum.auto()
    """Execute after successful method completion."""

    ERROR = enum.auto()
    """Execute when method raises an exception."""

    FINALLY = enum.auto()
    """Execute always (success or failure)."""


# Context variable for tracking current test during pytest runs
current_test_nodeid: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "current_test_nodeid", default=None
)
"""Context variable holding the current pytest test node ID.

This is used internally for test isolation and debugging.
"""


class HandlerRegistry:
    """Thread-safe handler registration and lookup.

    This class manages the event handler registry with thread-safe operations
    for registration, lookup, and predicate evaluation.

    THREAD SAFETY: All public methods are protected by self._lock (threading.RLock)
    to ensure safe concurrent access during handler registration and event dispatch.

    The registry uses a nested defaultdict structure:
        _events[event_name][priority] = [HandlerRegistration, ...]

    Higher priority values execute first. Within a priority level, handlers
    execute in registration order.
    """

    def __init__(self, debug: bool = False):
        """Initialize handler registry with thread-safe lock.

        Args:
            debug: Enable debug logging for handler operations
        """
        self._lock = threading.RLock()
        """RLock for thread-safe handler registration and access."""

        self._events: dict[EventName, dict[EventPriority, list[HandlerRegistration]]] = (
            collections.defaultdict(lambda: collections.defaultdict(list))
        )
        """Nested dict: event_name -> priority -> list of handlers."""

        self._debug = debug
        """Enable debug logging."""

        self._broadcast_to: list[HandlerRegistry] = []
        """List of other registries to forward events to."""

        self._next_handler_id: int = 0
        """Auto-incrementing counter for unique handler IDs."""

        self._handler_map: dict[int, tuple[EventName, EventPriority, HandlerRegistration]] = {}
        """Mapping from handler ID to (event, priority, registration) for deregistration."""

    def register_handler(
        self,
        event: EventName,
        handler: Callable[..., Any],
        priority: EventPriority = 100,
        predicate: Callable[[EventContext], bool] | None = None,
    ) -> int:
        """Register a handler for an event with thread safety.

        This method is thread-safe and can be called concurrently from multiple
        threads. If the handler is already registered for this event at this
        priority, its predicate will be updated and the existing handler ID is returned.

        Args:
            event: Event name to register handler for
            handler: Callable handler function or method
            priority: Execution priority (higher = earlier, default: 100)
            predicate: Optional condition for handler execution

        Returns:
            Unique handler ID that can be used with deregister()

        THREAD SAFETY: Protected by self._lock
        """
        with self._lock:
            registrations = self._events[event][priority]

            # Check if handler already registered at this priority
            for handler_id, (
                reg_event,
                reg_priority,
                registration,
            ) in self._handler_map.items():
                if (
                    reg_event == event
                    and reg_priority == priority
                    and registration.handler is handler
                ):
                    # Update predicate for existing handler
                    registration.predicate = predicate
                    if self._debug:
                        logger.debug(f"Updated predicate for {handler.__name__} on {event!r}")
                    return handler_id

            # Add new registration with unique ID
            handler_id = self._next_handler_id
            self._next_handler_id += 1

            registration = HandlerRegistration(handler=handler, predicate=predicate)
            registrations.append(registration)
            self._handler_map[handler_id] = (event, priority, registration)

            if self._debug:
                logger.debug(
                    f"Registered {handler.__name__} for {event!r} at priority {priority} (ID: {handler_id})"
                )

            return handler_id

    def deregister(self, handler_id: int) -> bool:
        """Remove a handler by its ID.

        This method is thread-safe and can be called during event emission
        without causing crashes or race conditions.

        Args:
            handler_id: Unique handler ID returned from register_handler()

        Returns:
            True if handler was found and removed, False if not found

        THREAD SAFETY: Protected by self._lock
        """
        with self._lock:
            if handler_id not in self._handler_map:
                return False

            event, priority, registration = self._handler_map[handler_id]

            # Remove from event handler list
            if event in self._events and priority in self._events[event]:
                try:
                    self._events[event][priority].remove(registration)
                    if self._debug:
                        logger.debug(f"Deregistered handler ID {handler_id} for {event!r}")
                except ValueError:
                    # Handler was already removed (edge case)
                    pass

            # Remove from handler map
            del self._handler_map[handler_id]
            return True

    def get_sorted_handlers(
        self,
        event: EventName,
        include_broadcasts: bool = True,
        _visited: set[int] | None = None,
    ) -> list[HandlerRegistration]:
        """Get all handlers for an event, sorted by priority (high to low).

        This method returns handlers sorted by priority in descending order
        (higher priorities execute first). If include_broadcasts is True,
        also includes handlers from broadcast target registries.

        Args:
            event: Event name to lookup handlers for
            include_broadcasts: Include handlers from broadcast targets

        Returns:
            List of HandlerRegistration instances sorted by priority

        THREAD SAFETY: Protected by self._lock for reading handler list
        """
        handlers: list[HandlerRegistration] = []

        if _visited is None:
            _visited = set()

        registry_id = id(self)
        if registry_id in _visited:
            return handlers

        _visited.add(registry_id)

        with self._lock:
            # Get handlers from this registry
            # Collect handlers for both exact match and wildcard
            matches = []
            if event in self._events:
                matches.append(self._events[event])

            # Add wildcard handlers if this isn't already a wildcard lookup
            if event != "*" and "*" in self._events:
                matches.append(self._events["*"])

            # Merge and sort priorities
            if matches:
                # Use a set to collect all unique priority levels
                all_priorities: set[EventPriority] = set()
                for match in matches:
                    all_priorities.update(match.keys())

                # Sort priorities descending
                priorities = sorted(all_priorities, reverse=True)

                for priority in priorities:
                    # Add exact match handlers first
                    if event in self._events and priority in self._events[event]:
                        handlers.extend(self._events[event][priority])

                    # Then add wildcard handlers
                    if event != "*" and "*" in self._events and priority in self._events["*"]:
                        handlers.extend(self._events["*"][priority])

            # Get handlers from broadcast targets
            if include_broadcasts:
                for target in self._broadcast_to:
                    # Recursive call to get handlers from broadcast targets
                    handlers.extend(
                        target.get_sorted_handlers(
                            event,
                            include_broadcasts=True,
                            _visited=_visited,
                        )
                    )

        return handlers

    def should_run_handler(self, registration: HandlerRegistration, ctx: EventContext) -> bool:
        """Check if handler should run based on its predicate.

        If the handler has no predicate, it always runs. If it has a predicate,
        the predicate is called with the context. If the predicate raises an
        exception, the handler is skipped and the exception is logged.

        Args:
            registration: Handler registration with optional predicate
            ctx: Event context to pass to predicate

        Returns:
            True if handler should execute, False to skip

        THREAD SAFETY: This method doesn't modify state, so no lock needed
        """
        predicate = registration.predicate
        if predicate is None:
            return True

        try:
            return bool(predicate(ctx))
        except Exception as e:
            if self._debug:
                logger.warning(
                    f"Predicate failed for {registration.handler.__name__}: {e}",
                    exc_info=True,
                )
            return False

    def add_broadcast_target(self, target: HandlerRegistry) -> int:
        """Add another registry to receive our events.

        Events dispatched through this registry will also be dispatched to
        the target registry, allowing for event forwarding and composition.

        Args:
            target: Another HandlerRegistry to forward events to

        Returns:
            Index of the added target in the broadcast list

        THREAD SAFETY: Protected by self._lock
        """
        with self._lock:
            if target not in self._broadcast_to:
                self._broadcast_to.append(target)
                return len(self._broadcast_to) - 1
            return self._broadcast_to.index(target)

    def get_handler_count(self, event: EventName | None = None) -> int:
        """Get count of registered handlers.

        Args:
            event: Optional event name to count handlers for.
                   If None, returns total handler count across all events.

        Returns:
            Number of registered handlers

        THREAD SAFETY: Protected by self._lock
        """
        with self._lock:
            if event is not None:
                if event not in self._events:
                    return 0
                count = sum(len(handlers) for handlers in self._events[event].values())
                return count
            else:
                # Total across all events
                return sum(
                    len(handlers)
                    for event_handlers in self._events.values()
                    for handlers in event_handlers.values()
                )
