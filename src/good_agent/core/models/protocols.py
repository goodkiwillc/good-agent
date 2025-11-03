"""
CONTEXT: Protocol definitions for extensible model behaviors.
ROLE: Define interfaces for context configuration and other extensible behaviors
      that can be implemented by model classes throughout goodintel_core.
DEPENDENCIES: typing module for Protocol and runtime checking support.
ARCHITECTURE: Runtime-checkable protocols that enable polymorphic behavior across model hierarchies.
KEY EXPORTS: SupportsContextConfig
USAGE PATTERNS:
  1) Implement SupportsContextConfig for context-aware configuration management
  2) Use isinstance() checks for runtime type verification
  3) Extend protocols for additional behavioral interfaces
RELATED MODULES: .base (base model classes), .application (application models)
"""

from typing import (
    ContextManager,
    Protocol,
    Self,
    runtime_checkable,
)


@runtime_checkable
class SupportsContextConfig(Protocol):
    def config(
        self,
        **kwargs,
    ) -> ContextManager[Self]: ...
