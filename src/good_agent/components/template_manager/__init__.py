"""Template Manager - Agent component for template rendering with context injection.

This package provides the TemplateManager component and supporting functionality
for managing Jinja2 templates with agent-specific features.

ORGANIZATION:
- core.py: TemplateManager component, Template class, global context providers
- injection.py: Context dependency injection for templates
- storage.py: Template storage backends and caching
- index.py: Template metadata and indexing

PUBLIC API:
Main exports for agent integration:
- TemplateManager: Agent component for template management
- Template: Template wrapper with context resolution
- global_context_provider: Decorator for registering global context providers

Context injection:
- ContextValue: Descriptor for injecting context values
- ContextResolver: Resolves context dependencies

Storage and metadata:
- FileSystemStorage: File-based template storage
- TemplateMetadata: Template metadata model

USAGE:
    from good_agent.components.template_manager import (
        TemplateManager,
        Template,
        global_context_provider,
    )

    # TemplateManager is automatically registered as an agent component
    agent = Agent(template_manager=TemplateManager())

    # Access via agent
    result = agent.template.render("my_template", context={"key": "value"})
"""

from __future__ import annotations

# Core template functionality
from .core import (
    Template,
    TemplateManager,
    _GLOBAL_CONTEXT_PROVIDERS,
    find_prompts_directory,
    find_user_prompts_directory,
    global_context_provider,
)

# Context dependency injection
from .injection import (
    CircularDependencyError,
    ContextInjectionError,
    ContextProviderError,
    ContextResolver,
    ContextValue,
    MissingContextValueError,
)

# Storage and metadata
from .index import TemplateMetadata
from .storage import (
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
