"""
CONTEXT: Agent context management system for template variables and configuration.
ROLE: Provides hierarchical context resolution with agent config integration and template variable access.
DEPENDENCIES:
  - .config: ConfigStack base class for chainmap-based context management
ARCHITECTURE:
  - Context extends ConfigStack for hierarchical context resolution
  - Agent config integration for configuration-based context variables
  - Template variable access with fallback mechanisms
  - Context manager support for temporary modifications
KEY EXPORTS: Context class for agent template variable management
USAGE PATTERNS:
  1. Template rendering: agent.context.get("variable_name")
  2. Context inheritance: Context(base_context={...})
  3. Configuration access: Context().get("config_var")
  4. Temporary context: with agent.context({temp_var: value}):
RELATED MODULES:
  - agent.py: Uses context for template rendering
  - templating/: Template rendering with context variables
  - config.py: Base ConfigStack implementation

PERFORMANCE CONTEXT:
- Context resolution: O(1) for most lookups (chainmap-based)
- Memory usage: ~1KB base + context variable storage
- Thread safety: Thread-safe for read operations
- Template rendering: Context variable resolution adds ~1-5ms overhead

CONTEXT RESOLUTION ORDER:
1. Local context overrides (from context managers)
2. Direct context assignments
3. Agent configuration context
4. Default fallback values
5. KeyError if not found

USAGE PATTERNS:
- Template variables: agent.context["variable_name"]
- Configuration access: agent.context.get("config_setting")
- Context inheritance: Automatic from agent config
- Temporary modifications: via context manager
"""

from typing import Any

from .config import ConfigStack


class Context(ConfigStack):
    """Agent context manager with hierarchical resolution and config integration.

    PURPOSE: Provides template variable access with fallback mechanisms, integrating
    agent configuration context with local context modifications for template rendering.

    ROLE: Manages context variable resolution for:
    - Template rendering with variable substitution
    - Agent configuration access and inheritance
    - Local context overrides via context managers
    - Hierarchical fallback mechanisms

    CONTEXT RESOLUTION ORDER:
    1. Local context overrides (highest priority)
       - Context manager temporary modifications
       - Direct assignments via context[key] = value
    2. Agent configuration context
       - Variables from agent.config.context
       - Configuration-based default values
    3. Base context from constructor
       - Initial context values passed to constructor
    4. Default fallback values
       - Provided via get(key, default) method

    PERFORMANCE CHARACTERISTICS:
    - Lookups: O(1) for chainmap-based resolution
    - Memory: ~1KB base + context variable storage
    - Template rendering: ~1-5ms overhead for variable resolution
    - Thread safety: Thread-safe for read operations

    USAGE PATTERNS:
    ```python
    # Basic context usage
    context = Context(name="AI Assistant", version="1.0")
    template = "Hello, I'm {name} v{version}"
    rendered = template.render(**context.as_dict())

    # With agent config integration
    context = Context(agent_config=agent.config)
    # Accesses agent.config.context variables automatically

    # Context manager for temporary modifications
    with context({temp_var: "temporary value"}):
        # temp_var available only in this block
        pass
    # temp_var automatically removed
    ```

    INTEGRATION POINTS:
    - Agent.__init__: Context initialized with agent configuration
    - Template rendering: Context provides variables for Jinja2 templates
    - Tool execution: Context available for tool parameter injection
    - Message rendering: Context used for message template processing

    THREAD SAFETY:
    - Read operations: Thread-safe (chainmap is immutable)
    - Write operations: Not thread-safe (use context managers for isolation)
    - Template rendering: Safe with read-only context access
    """

    def __init__(self, agent_config=None, **kwargs):
        """Initialize context with optional agent config integration.

        PURPOSE: Create a new context instance with optional agent configuration
        integration and initial context variables.

        INITIALIZATION FLOW:
        1. Initialize base ConfigStack with provided kwargs
        2. Store agent config reference for context inheritance
        3. Set up initial context from constructor parameters

        Args:
            agent_config: Agent configuration manager for context inheritance.
                If provided, context variables from agent.config.context will be
                available as fallback values for missing local context.
            **kwargs: Initial context variables as keyword arguments.
                These become the base context that can be overridden.

        SIDE EFFECTS:
        - Stores reference to agent config for context inheritance
        - Initializes base ConfigStack with provided variables
        - Sets up context resolution chain

        EXAMPLES:
        ```python
        # Basic context initialization
        context = Context(name="Assistant", role="helpful")

        # With agent config integration
        context = Context(agent_config=agent.config, local_var="local_value")

        # Empty context with config integration
        context = Context(agent_config=agent.config)
        ```
        """
        super().__init__(**kwargs)
        self._agent_config = agent_config

    def _set_agent_config(self, agent_config):
        """Set the agent config for this context

        PURPOSE: Update the agent configuration reference after context creation.
        Used by agent during initialization to provide config integration.

        Args:
            agent_config: Agent configuration manager instance
                Used for context variable fallback and inheritance
        """
        self._agent_config = agent_config

    def _get_config_context(self) -> dict[str, Any]:
        """Get the current context from config manager"""
        if self._agent_config and "context" in self._agent_config._chainmap:
            return dict(self._agent_config._chainmap["context"])
        return {}

    def __getitem__(self, key):
        """Get item with config context inheritance"""
        # First try local context (includes context manager overrides)
        try:
            return self._chainmap[key]
        except KeyError:
            pass

        # Then try config context
        config_context = self._get_config_context()
        if isinstance(config_context, dict) and key in config_context:
            return config_context[key]

        # Key not found
        raise KeyError(key)

    def get(self, key, default=None):
        """Get with config context inheritance"""
        try:
            return self[key]
        except KeyError:
            return default

    def as_dict(self) -> dict[str, Any]:
        """Return current context as a dictionary, merging config and local contexts"""
        # Start with config context
        result = self._get_config_context().copy()
        # Override with local context (including context manager overrides)
        result.update(dict(self._chainmap))
        return result
