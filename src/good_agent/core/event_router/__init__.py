"""Re-export the EventRouter package's public API under one import path."""

from __future__ import annotations

# Advanced features
from good_agent.core.event_router.advanced import TypedApply

# Event context
from good_agent.core.event_router.context import EventContext, event_ctx

# Main EventRouter class
from good_agent.core.event_router.core import EventRouter

# Decorators
from good_agent.core.event_router.decorators import (
    EventHandlerDecorator,
    emit,
    emit_event,
    on,
    typed_on,
)

# Core protocols and types
from good_agent.core.event_router.protocols import (
    ApplyInterrupt,
    EventName,
    EventPriority,
    PredicateHandler,
)

# Handler registration and lifecycle
from good_agent.core.event_router.registration import (
    HandlerRegistration,
    LifecyclePhase,
    current_test_nodeid,
)

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
    "PredicateHandler",
    "EventHandlerDecorator",
    # Test infrastructure
    "current_test_nodeid",
    # Context variable (advanced usage)
    "event_ctx",
]
