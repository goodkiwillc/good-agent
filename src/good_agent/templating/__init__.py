# Provide type aliases and core registries required during import
# Importing from core templating avoids circular imports with this package
from good_agent.core.templating import (  # re-export for compatibility
    TEMPLATE_REGISTRY,
    TemplateLike,
    TemplateRegistry,
    add_named_template,
    create_environment,
    get_named_template,
    render_template,
)

# Core template functionality
from .core import (
    _GLOBAL_CONTEXT_PROVIDERS,  # Needed by some tests
    Template,
    TemplateManager,
    find_prompts_directory,
    find_user_prompts_directory,
    global_context_provider,
)

# Environment creation utilities
from .environment import (
    create_simple_template_environment,
    create_template_environment,
    get_default_environment,
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

__all__ = [
    # Core
    "Template",
    "TemplateManager",
    "global_context_provider",
    "find_prompts_directory",
    "find_user_prompts_directory",
    # Environment
    "create_template_environment",
    "create_simple_template_environment",
    "get_default_environment",
    "_GLOBAL_CONTEXT_PROVIDERS",
    # Types
    "TemplateLike",
    # Core registries/utilities from core.templating
    "TemplateRegistry",
    "TEMPLATE_REGISTRY",
    "add_named_template",
    "get_named_template",
    "create_environment",
    "render_template",
    # Context dependency injection
    "ContextValue",
    "ContextResolver",
    "ContextInjectionError",
    "MissingContextValueError",
    "ContextProviderError",
    "CircularDependencyError",
]
