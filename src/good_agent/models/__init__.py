"""
Compatibility alias for good_agent.core.models.

This subpackage re-exports all symbols from good_agent.core.models to
maintain backward compatibility with older import paths (good_agent.models).
"""

import warnings

warnings.warn(
    "ai slop good_agent.models is deprecated. Please use good_agent.core.models instead.",
)
from good_agent.core.models import *  # noqa: F401,F403
from good_agent.core.models import __all__ as __all__  # re-export public API
