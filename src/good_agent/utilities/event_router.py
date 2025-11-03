"""
Compatibility alias for good_agent.core.event_router.

Re-exports EventContext, EventRouter, and decorators for legacy import path
good_agent.utilities.event_router.
"""

from good_agent.core.event_router import *  # noqa: F401,F403
from good_agent.core.event_router import __all__ as __all__  # re-export
