# coverage: ignore file
# Rationale: module aggregates template manager exports for convenience only.
"""Exports the template manager component plus helpers.

See ``examples/templates/render_template.py`` for inline rendering patterns that
use this package.
"""

from __future__ import annotations

# Core template functionality
from good_agent.extensions.template_manager.core import (
    Template,
    TemplateManager,
    _GLOBAL_CONTEXT_PROVIDERS,
    find_prompts_directory,
    find_user_prompts_directory,
    global_context_provider,
)

# Context dependency injection
from good_agent.extensions.template_manager.injection import (
    CircularDependencyError,
    ContextInjectionError,
    ContextProviderError,
    ContextResolver,
    ContextValue,
    MissingContextValueError,
)

# Storage and metadata
from good_agent.extensions.template_manager.index import TemplateMetadata
from good_agent.extensions.template_manager.storage import (
    ChainedStorage,
    FileSystemStorage,
    StorageTemplateLoader,
    TemplateSnapshot,
    TemplateStorage,
    TemplateValidator,
)

__all__ = [
    # Core
    "Template",
    "TemplateManager",
    "global_context_provider",
    "find_prompts_directory",
    "find_user_prompts_directory",
    "_GLOBAL_CONTEXT_PROVIDERS",
    # Context injection
    "ContextValue",
    "ContextResolver",
    "ContextInjectionError",
    "MissingContextValueError",
    "ContextProviderError",
    "CircularDependencyError",
    # Storage
    "TemplateStorage",
    "FileSystemStorage",
    "ChainedStorage",
    "StorageTemplateLoader",
    "TemplateSnapshot",
    "TemplateValidator",
    # Metadata
    "TemplateMetadata",
]
