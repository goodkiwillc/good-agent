"""
Compatibility alias for good_agent.core.models.

This subpackage re-exports all symbols from good_agent.core.models to
maintain backward compatibility with older import paths (good_agent.models).
"""

from good_agent.core.models import *  # noqa: F401,F403
from good_agent.core.models import __all__ as __all__  # re-export public API
