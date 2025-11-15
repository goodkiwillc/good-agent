"""Public API for the event_router package.

This module re-exports all public symbols from the reorganized event_router
package, maintaining full backward compatibility with the original monolithic
event_router.py module.

ORGANIZATION:
- protocols.py: Type definitions, protocols, exceptions
- context.py: EventContext and context variables
- registration.py: HandlerRegistration, LifecyclePhase, and registry
- sync_bridge.py: SyncBridge for async/sync interoperability
- decorators.py: @on, @emit, @typed_on decorators
- core.py: EventRouter main class
- advanced.py: TypedApply helper for type-safe event dispatch

BACKWARD COMPATIBILITY:
All imports that previously worked with:
    from good_agent.core.event_router import EventRouter, EventContext, on, emit

...continue to work identically with the new package structure.

USAGE:
    from good_agent.core.event_router import (
        EventRouter,     # Main event routing class
        EventContext,    # Event context for handler chains
        ApplyInterrupt,  # Exception for early termination
        on,              # Decorator for event handlers
        emit,            # Decorator for lifecycle events
        typed_on,        # Type-safe @on variant
        emit_event,      # Function-style emit decorator
        TypedApply,      # Helper for typed event dispatch
        LifecyclePhase,  # Enum for lifecycle phases
    )

THREAD SAFETY:
All exported components are thread-safe:
- EventRouter: Thread-safe via HandlerRegistry's RLock
- EventContext: Thread-safe via contextvars propagation
- Decorators: Stateless and thread-safe
- TypedApply: Thread-safe (immutable router reference)
"""

from __future__ import annotations

# Core protocols and types
from .protocols import (
    ApplyInterrupt,
    EventName,
    EventPriority,
)

# Event context
from .context import EventContext, event_ctx

# Handler registration and lifecycle
from .registration import HandlerRegistration, LifecyclePhase, current_test_nodeid

# Decorators
from .decorators import EventHandlerDecorator, emit, emit_event, on, typed_on

# Main EventRouter class
from .core import EventRouter

# Advanced features
from .advanced import TypedApply

# Public API - maintains backward compatibility with original event_router.py
__all__ = [
    # Core classes
    "EventRouter",
    "EventContext",
    "ApplyInterrupt",
    "TypedApply",
    # Decorators
    "on",
    "typed_on",
    "emit",
    "emit_event",
    # Registration and lifecycle
    "LifecyclePhase",
    "HandlerRegistration",
    # Type aliases
    "EventName",
    "EventPriority",
    "EventHandlerDecorator",
    # Test infrastructure
    "current_test_nodeid",
    # Context variable (advanced usage)
    "event_ctx",
]
