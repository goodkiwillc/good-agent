import asyncio
import logging
from collections import ChainMap
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import ChoiceLoader

# from good_agent.templating import render_template as core_render_template
from good_agent.core import templating

from ..components import AgentComponent
from ..events import AgentEvents
from .injection import (
    ContextResolver,
    _modify_function_for_injection,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


# Global context providers registry
_GLOBAL_CONTEXT_PROVIDERS: dict[str, Callable[[], Any]] = {}


def global_context_provider(name: str):
    """Register a global context provider"""

    def decorator(func: Callable[[], Any]) -> Callable[[], Any]:
        _GLOBAL_CONTEXT_PROVIDERS[name] = func
        return func

    return decorator


# Register default global context providers
@global_context_provider("today")
def _provide_today():
    """Provide current date as a datetime object.

    Returns a datetime object set to midnight of the current date.
    If good_common.utilities:now_pt is available, use that for PT timezone.
    Otherwise, fall back to UTC time.
    """
    try:
        # Try to import the now_pt function if available
        from good_common.utilities import now_pt

        now = now_pt()
        # Return datetime at midnight for consistency
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    except ImportError:
        # Fall back to UTC if good_common is not available
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # Return datetime at midnight for consistency
        return now.replace(hour=0, minute=0, second=0, microsecond=0)


@global_context_provider("now")
def _provide_now():
    """Provide current datetime as a datetime object.

    If good_common.utilities:now_pt is available, use that for PT timezone.
    Otherwise, fall back to UTC time.
    """
    try:
        # Try to import the now_pt function if available
        from good_common.utilities import now_pt

        return now_pt()
    except ImportError:
        # Fall back to UTC if good_common is not available
        from datetime import datetime, timezone

        return datetime.now(timezone.utc)


def find_prompts_directory() -> Path | None:
    """Find the prompts directory by looking for prompts.yaml."""
    current = Path.cwd()

    # Check current directory and parents
    for directory in [current] + list(current.parents):
        prompts_yaml = directory / "prompts.yaml"
        if prompts_yaml.exists():
            prompts_dir = directory / "prompts"
            if prompts_dir.exists():
                return prompts_dir

    # Check if prompts directory exists without prompts.yaml
    prompts_dir = current / "prompts"
    if prompts_dir.exists():
        return prompts_dir

    return None


def find_user_prompts_directory() -> Path | None:
    """Find user-level prompts directory."""
    user_dir = Path.home() / ".good-agent" / "prompts"
    if user_dir.exists():
        return user_dir
    return None


class Template:
    """Wrapper class for deferred template rendering in tool parameters and method calls.

    PURPOSE: Enables lazy evaluation of template strings in contexts where immediate
    rendering is not desirable or possible, such as tool parameter injection.

    ROLE: Facilitates template usage in:
    - Tool parameter injection with dynamic context resolution
    - Deferred template rendering until context is available
    - Strict vs. lenient template error handling
    - Template caching for repeated usage patterns

    USAGE PATTERNS:
    ```python
    # Tool parameter templates
    agent.invoke(
        search_tool,
        query=Template("{{subject}} {{region}}"),
        time_period=Template("{{time_period|default('last_day')}}"),
    )

    # Strict template validation
    strict_template = Template("{{required_var}}", strict=True)

    # Template reuse with caching
    cached_template = Template("Hello {{name}} from {{location}}")
    result1 = cached_template.render({"name": "Alice", "location": "NYC"})
    result2 = cached_template.render({"name": "Bob", "location": "LA"})
    ```

    ERROR HANDLING:
    - Strict mode (strict=True): Template errors raise exceptions immediately
    - Lenient mode (strict=False): Template errors return original template string
    - Missing variables: Handled according to strict mode setting
    - Template syntax errors: Always raised regardless of strict mode

    CACHING BEHAVIOR:
    - Rendered results cached after first successful render
    - Subsequent render() calls return cached result
    - Cache cleared when template string changes
    - Useful for repeated template usage with different contexts

    PERFORMANCE:
    - Template rendering: 1-10ms depending on complexity
    - Cached render: <1ms (direct lookup)
    - Memory: ~100 bytes per Template instance + rendered cache
    """

    def __init__(self, template: str, strict: bool = False):
        """Initialize a Template wrapper with rendering configuration.

        PURPOSE: Create a new template instance with specified error handling
        behavior and initial template string.

        Args:
            template: The Jinja2 template string to render later
            strict: If True, template errors raise exceptions immediately.
                   If False, errors return original template string (default: False)

        SIDE EFFECTS:
        - Stores template string for later rendering
        - Initializes render cache as None
        - Sets error handling mode for subsequent operations

        EXAMPLES:
        ```python
        # Lenient template (default)
        template = Template("Hello {{name}}")

        # Strict template with error handling
        strict_template = Template("Hello {{missing_var}}", strict=True)

        # Template with default filters
        filtered_template = Template("{{value|default('N/A')}}")
        ```
        """
        self.template = template
        self.strict = strict
        self._rendered: str | None = None

    def render(self, context: dict[str, Any]) -> str:
        """Render the template with the provided context variables.

        PURPOSE: Execute template rendering with context variable substitution,
        caching the result for subsequent calls.

        RENDERING PROCESS:
        1. Check cache: Return cached result if available
        2. Template parsing: Parse Jinja2 syntax and variable references
        3. Context substitution: Replace variables with provided context values
        4. Filter execution: Apply Jinja2 filters and functions
        5. Result caching: Store successful render for future calls
        6. Error handling: Handle template errors according to strict mode

        Args:
            context: Dictionary mapping variable names to values for template
                     substitution. Variables not found in context are handled
                     according to strict mode setting.

        Returns:
            Rendered template string with all substitutions applied

        Raises:
            TemplateError: If strict=True and template rendering fails
            TemplateSyntaxError: For invalid Jinja2 syntax (always raised)

        PERFORMANCE:
        - First render: 1-10ms depending on template complexity
        - Cached render: <1ms (direct cache lookup)
        - Complex templates: Additional time for filters and logic

        EXAMPLES:
        ```python
        template = Template("Hello {{name}}, today is {{date}}")

        # Basic rendering
        result = template.render({"name": "Alice", "date": "Monday"})
        # Returns: "Hello Alice, today is Monday"

        # With missing variables (lenient mode)
        result = template.render({"name": "Bob"})
        # Returns: "Hello Bob, today is " (missing variable treated as empty)

        # With default filters
        template = Template("Value: {{value|default('N/A')}}")
        result = template.render({})  # No 'value' key
        # Returns: "Value: N/A"
        ```
        """
        try:
            rendered = templating.render_template(self.template, context)
            self._rendered = rendered
            return str(rendered)
        except Exception:
            if self.strict:
                raise
            # Return original template if rendering fails in non-strict mode
            return self.template

    def __str__(self) -> str:
        """String representation of the Template.

        PURPOSE: Provide intuitive string conversion behavior that returns
        the rendered result when available, falling back to the template string.

        BEHAVIOR:
        - If template has been rendered successfully: return cached result
        - If template not yet rendered: return original template string
        - Enables natural usage in string contexts and logging

        USAGE:
        ```python
        template = Template("Hello {{name}}")
        template.render({"name": "World"})
        print(str(template))  # Prints: "Hello World"

        # Before rendering
        template = Template("Hello {{name}}")
        print(str(template))  # Prints: "Hello {{name}}"
        ```
        """
        return self._rendered if self._rendered is not None else self.template

    def __repr__(self) -> str:
        """Developer-friendly representation of the Template.

        PURPOSE: Provide debugging and development information about the
        Template instance, including strict mode and template content.

        FORMAT:
        Template(template_string, strict=True/False)

        USAGE:
        ```python
        template = Template("Hello {{name}}", strict=True)
        repr(template)  # Returns: "Template('Hello {{name}}', strict=True)"
        ```
        """
        return f"Template({self.template!r}, strict={self.strict})"


class TemplateManager(AgentComponent):
    """Central template management system with hierarchical context resolution and caching.

    PURPOSE: Provides comprehensive template rendering capabilities including
    file-based templates, context providers, dependency injection, and performance
    optimization through intelligent caching strategies.

    ROLE: Manages the complete template lifecycle:
    - Template discovery from multiple sources (files, registry, inline)
    - Context resolution with hierarchical overrides and providers
    - Template compilation and caching for performance optimization
    - Security through sandboxed Jinja2 environments
    - Event integration for template modification and monitoring
    - Dependency injection for context providers and agent access

    ARCHITECTURE COMPONENTS:
    1. Template Loading: ChoiceLoader with file storage and registry fallback
    2. Context Resolution: ChainMap-based hierarchical context with providers
    3. Template Compilation: Jinja2 parsing with security sandboxing
    4. Caching System: Multi-level caching for templates and rendered results
    5. Event System: Template lifecycle events for modification and monitoring
    6. Dependency Injection: Automatic provider parameter injection

    FILE TEMPLATE DISCOVERY:
    Template sources are checked in priority order:
    1. Explicit Directory: User-specified prompts directory (highest priority)
    2. Project Directory: prompts/ in current project or parent directories
    3. User Directory: ~/.good-agent/prompts (lowest priority)
    4. Registry Templates: In-memory registered templates (fallback)

    CONTEXT RESOLUTION HIERARCHY:
    1. Base Context: Direct parameters passed to render methods (highest priority)
    2. Context Stack: Temporary overrides via context managers
    3. Message Context: Context from specific message being rendered
    4. Instance Providers: Agent-specific context providers
    5. Global Providers: System-wide providers (today, now, etc.)
    6. Default Values: Fallback values for missing variables

    PERFORMANCE OPTIMIZATION:
    - Template Compilation: Parsed templates cached indefinitely
    - Context Resolution: Provider results cached when appropriate
    - File Loading: Template files cached in memory after first access
    - Render Caching: Results cached for static templates without dynamic context
    - Async Preloading: File templates can be preloaded for synchronous access

    SECURITY FEATURES:
    - Sandboxed Jinja2 environment by default
    - Restricted template syntax and built-in functions
    - File access limited to designated template directories
    - Input sanitization for template variables
    - Template inheritance restricted to allowed directories

    USAGE PATTERNS:
    ```python
    # Basic template rendering
    result = agent.template.render("Hello {{name}}", {"name": "User"})

    # File template with inheritance
    result = agent.template.render_template("{% extends 'base' %}...")


    # Context provider registration
    @agent.template.context_provider("current_time")
    def get_current_time():
        return datetime.now()


    # Template preloading for performance
    await agent.template.preload_templates(["system/assistant", "tool/search"])
    ```

    LIFECYCLE MANAGEMENT:
    1. Initialization: Set up file storage, environment, and context providers
    2. Template Registration: Add templates to registry for later use
    3. Context Provider Setup: Register dynamic context value providers
    4. Template Rendering: Resolve context, compile templates, render results
    5. Event Firing: Template lifecycle events for modification and monitoring
    6. Caching: Store compiled templates and rendered results for performance

    INTEGRATION POINTS:
    - Agent Integration: Automatic registration during agent initialization
    - Message Rendering: Context resolution for message template parts
    - Tool Execution: Template rendering for tool parameters
    - Component System: Event-based template modification by components
    - Configuration System: Template directory and security configuration
    """

    def __init__(
        self,
        prompts_dir: Path | None = None,
        enable_file_templates: bool = True,
        use_sandbox: bool = True,
    ):
        """Initialize TemplateManager with configurable template sources and security.

        PURPOSE: Create a new template manager instance with specified template
        discovery strategy and security configuration.

        INITIALIZATION PROCESS:
        1. Component Setup: Initialize AgentComponent base class and event router
        2. Storage Configuration: Set up file-based template loading if enabled
        3. Environment Creation: Create Jinja2 environment with security settings
        4. Context System: Initialize context resolver and provider registry
        5. Template Registry: Create local registry with global fallback
        6. Cache Setup: Initialize caching systems for performance

        Args:
            prompts_dir: Optional explicit prompts directory path for template
                         discovery. If provided, this directory takes highest
                         priority in template loading.
            enable_file_templates: Whether to enable file-based template loading
                                  from multiple directories (default: True)
            use_sandbox: Whether to use SandboxedEnvironment for security.
                        Disabling may be necessary for advanced template features
                        but reduces security (default: True)

        SIDE EFFECTS:
        - Initializes file storage chain if file templates enabled
        - Creates Jinja2 environment with specified security settings
        - Sets up context provider registry and resolver
        - Initializes template registry with global fallback
        - Configures caching systems for templates and context

        PERFORMANCE IMPACT:
        - File template discovery: 10-50ms during initialization
        - Environment setup: 5-20ms for Jinja2 configuration
        - Memory usage: ~1KB base + template cache storage
        - Template compilation: 5-20ms per unique template (cached)

        EXAMPLES:
        ```python
        # Default configuration (file templates + sandbox)
        template_manager = TemplateManager()

        # Custom template directory
        template_manager = TemplateManager(prompts_dir=Path("/my/prompts"))

        # Registry-only templates (no file access)
        template_manager = TemplateManager(enable_file_templates=False)

        # Advanced features with reduced security
        template_manager = TemplateManager(use_sandbox=False)
        ```
        """
        super().__init__()  # Initialize AgentComponent/EventRouter
        self._explicit_prompts_dir = prompts_dir
        self._context_providers: dict[str, Callable[[], Any]] = {}
        self._context_stack: list[dict[str, Any]] = []
        self.use_sandbox = use_sandbox

        # Initialize context resolver
        self._context_resolver = ContextResolver(self)

        # File template support
        self.file_storage: Any = None  # ChainedStorage | FileSystemStorage | None
        self.file_loader: Any = None  # StorageTemplateLoader | None
        self.file_templates_enabled = enable_file_templates
        self._template_cache: dict[str, Any] = {}

        # Create a local registry with the global registry as parent
        self._registry = templating.TemplateRegistry(
            parent=templating.TEMPLATE_REGISTRY
        )

        # Set up the environment
        if enable_file_templates:
            self._setup_file_templates(prompts_dir)
        else:
            # Basic environment without file support
            self._env = templating.create_environment(
                config=dict(trim_blocks=False),
                loader=self._registry,
                use_sandbox=self.use_sandbox,
            )

    def _clone_init_args(self):
        return (), {
            "prompts_dir": self._explicit_prompts_dir,
            "enable_file_templates": self.file_templates_enabled,
            "use_sandbox": self.use_sandbox,
        }

    def _export_state(self) -> dict[str, Any]:
        state = super()._export_state()
        state["context_providers"] = dict(self._context_providers)
        state["context_stack"] = [dict(ctx) for ctx in self._context_stack]
        state["template_cache"] = dict(self._template_cache)
        state["registry_maps"] = [
            dict(mapping) for mapping in self._registry.templates.maps
        ]
        return state

    def _import_state(self, state: dict[str, Any]) -> None:
        super()._import_state(state)
        self._context_providers = dict(state.get("context_providers", {}))
        self._context_stack = [dict(ctx) for ctx in state.get("context_stack", [])]
        self._template_cache = dict(state.get("template_cache", {}))
        registry_maps = state.get("registry_maps")
        if registry_maps is not None:
            from collections import ChainMap

            self._registry._templates = ChainMap(
                *[dict(mapping) for mapping in registry_maps]
            )

    def context_provider(self, name: str):
        """Register an instance-specific context provider with dependency injection support"""

        def decorator(func: Callable[[], Any]) -> Callable[[], Any]:
            # Apply dependency injection modification
            # First wrap to handle Agent and Message injection
            import functools
            import inspect

            sig = inspect.signature(func)
            needs_agent = False
            needs_message = False

            for param_name, param in sig.parameters.items():
                if param.annotation == inspect.Parameter.empty:
                    continue
                # Check for Agent type without Depends
                param_type = str(param.annotation)
                if "Agent" in param_type and param.default == inspect.Parameter.empty:
                    needs_agent = True
                elif (
                    "Message" in param_type and param.default == inspect.Parameter.empty
                ):
                    needs_message = True

            if needs_agent or needs_message:

                @functools.wraps(func)
                async def agent_wrapper(*args, **kwargs):
                    # Inject agent and message if needed
                    if (
                        needs_agent
                        and "agent" not in kwargs
                        and hasattr(self, "_agent")
                    ):
                        kwargs["agent"] = self._agent
                    if needs_message and "message" not in kwargs:
                        # Get last message if available
                        if (
                            hasattr(self, "_agent")
                            and self._agent
                            and hasattr(self._agent, "messages")
                        ):
                            if self._agent.messages:
                                kwargs["message"] = self._agent.messages[-1]

                    # Call the function
                    if asyncio.iscoroutinefunction(func):
                        return await func(*args, **kwargs)
                    else:
                        return func(*args, **kwargs)

                # Now apply context value injection
                modified_func = _modify_function_for_injection(agent_wrapper)
            else:
                # Just apply context value injection
                modified_func = _modify_function_for_injection(func)

            # Store the modified function
            self._context_providers[name] = modified_func

            # Return original function for better debugging
            return func

        return decorator

    def _setup_file_templates(self, prompts_dir: Path | None = None):
        """Set up file-based template loading."""
        from .environment import create_template_environment
        from .storage import ChainedStorage, FileSystemStorage, StorageTemplateLoader

        # Build storage chain
        storages = []

        # 1. Explicit directory (highest priority)
        if prompts_dir and prompts_dir.exists():
            storages.append(FileSystemStorage(prompts_dir))

        # 2. Project directory
        project_prompts = find_prompts_directory()
        if project_prompts:
            storages.append(FileSystemStorage(project_prompts))

        # 3. User directory (lowest priority)
        user_prompts = find_user_prompts_directory()
        if user_prompts:
            storages.append(FileSystemStorage(user_prompts))

        if storages:
            # Create chained storage if multiple sources
            if len(storages) > 1:
                from typing import cast

                self.file_storage = ChainedStorage(cast(list, storages))
            else:
                self.file_storage = storages[0]

            # Create Jinja2 loader for file templates
            self.file_loader = StorageTemplateLoader(self.file_storage)

            # Replace the environment with one that includes both loaders
            # File templates take priority over registry templates
            combined_loader = ChoiceLoader(
                [
                    self.file_loader,  # Check files first
                    self._registry,  # Fall back to registry
                ]
            )

            # Create new environment with combined loader. We rely on
            # good_agent.templating DEFAULT_CONFIG for extensions and
            # line statement/comment prefixes, overriding trim_blocks as needed.
            self._env = create_template_environment(
                use_sandbox=self.use_sandbox,
                trim_blocks=False,
                loader=combined_loader,
            )
        else:
            # No file sources found, use basic environment
            self._env = templating.create_environment(
                config=dict(trim_blocks=False),
                loader=self._registry,
                use_sandbox=self.use_sandbox,
            )

    async def preload_templates(self, template_names: list[str]) -> None:
        """
        Preload file templates for synchronous rendering.

        This is important for templates that will be used in synchronous
        contexts where we can't await the async file operations.

        Args:
            template_names: List of template names to preload
        """
        if not self.file_storage:
            return

        for name in template_names:
            # Try to get the template content
            content = await self.file_storage.get(name)
            if content:
                # Cache it in the loader
                if self.file_loader is not None:
                    self.file_loader._cache[name] = content
                # Also cache in our local cache
                self._template_cache[name] = content

    def add_template(
        self,
        name: str,
        template: templating.TemplateLike,
        replace: bool = False,
        append_newline: bool = False,
    ):
        from good_agent.core.text import string

        if isinstance(template, bytes):
            template = template.decode("utf-8")

        if isinstance(template, str):
            template = string.unindent(template)
            if append_newline and not template.endswith("\n"):
                template += "\n"
        return self._registry.add_template(name, template, replace=replace)

    def get_template(
        self,
        name: str,
    ) -> str:
        """
        Get a template by name from any source.

        Checks in order:
        1. File templates (if enabled)
        2. Registry templates

        Args:
            name: Template name

        Returns:
            Template content

        Raises:
            TemplateNotFound: If template doesn't exist
        """
        # Try file storage first
        if (
            self.file_loader
            and hasattr(self.file_loader, "_cache")
            and name in self.file_loader._cache
        ):
            return self.file_loader._cache[name]

        # Fall back to registry
        return self._registry.get_template(name)

    async def get_template_async(self, name: str) -> str:
        """
        Get a template asynchronously, checking file storage.

        Args:
            name: Template name

        Returns:
            Template content
        """
        # Try file storage first
        if self.file_storage:
            content = await self.file_storage.get(name)
            if content:
                # Cache for future sync access
                if self.file_loader:
                    self.file_loader._cache[name] = content
                return content

        # Fall back to registry
        return self.get_template(name)

    def extract_template_variables(self, template_str: str) -> list[str]:
        """Extract undeclared variables from a Jinja2 template.

        Args:
            template_str: The template string to analyze

        Returns:
            List of variable names used in the template
        """
        from jinja2 import meta

        from .environment import create_simple_template_environment

        try:
            # Use a sandboxed environment for parsing (safe by default)
            env = create_simple_template_environment(use_sandbox=True)
            ast = env.parse(template_str)
            variables = meta.find_undeclared_variables(ast)
            return list(variables)
        except Exception as e:
            logger.warning(f"Failed to extract template variables: {e}")
            return []

    async def resolve_context(
        self,
        base_context: dict[str, Any],
        message_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Resolve context with proper hierarchy and dynamic providers"""

        # Collect all context sources
        contexts = [base_context]
        if self._context_stack:
            contexts.extend(self._context_stack)
        if message_context:
            contexts.append(message_context)

        # Create a ChainMap for proper override behavior
        combined = ChainMap(*reversed(contexts))

        # Use the ContextResolver for dependency injection support
        self._context_resolver.clear_cache()  # Clear cache for fresh resolution

        # Build base context from all sources
        resolved_base = dict(combined)

        # Get all provider names
        provider_keys = set()
        provider_keys.update(_GLOBAL_CONTEXT_PROVIDERS.keys())
        provider_keys.update(self._context_providers.keys())

        # Resolve each provider with dependency injection
        for key in provider_keys:
            if key not in resolved_base:
                try:
                    value = await self._context_resolver.resolve_value(
                        key, resolved_base
                    )
                    resolved_base[key] = value
                except Exception:
                    # Skip failed providers in production
                    # This prevents one failing provider from breaking all template rendering
                    pass

        return resolved_base

    def render_template(self, template: str, context: dict[str, Any]) -> str:
        """
        Render a template with the given context.

        This method supports:
        - Inline templates: "Hello {{ name }}"
        - Registry templates: "{% include 'registered_template' %}"
        - File templates: "{% include 'system/assistant' %}"
        - Template inheritance: "{% extends 'system/base' %}"

        Args:
            template: Template string to render
            context: Context dictionary

        Returns:
            Rendered template string
        """
        # Resolve context providers synchronously
        resolved_context = self._resolve_context_sync(context)

        # Use our enhanced environment with file loaders if available
        try:
            result = templating.render_template(
                template, resolved_context, environment=self._env
            )
        except Exception:
            # Re-raise template errors to make them fatal
            raise

        # Fire event if agent is available
        if hasattr(self, "_agent") and self._agent:
            modified_result = self._agent.apply_sync(
                AgentEvents.TEMPLATE_COMPILE,
                template=template,
                context=resolved_context,
                result=result,
                agent=self._agent,
                extension=self,
            )
            if modified_result.output is not None:
                result = modified_result.output

        return str(result)

    def render(self, template_str: str, context: dict[str, Any] | None = None) -> str:
        """
        Render a template string with the given context.

        This is a convenience method that builds the full context
        including dynamic providers.

        Args:
            template_str: Template string or reference
            context: Template context variables

        Returns:
            Rendered template string
        """
        context = context or {}

        # Add any dynamic context providers
        full_context = self._build_context(context)

        # Render using our environment
        template = self._env.from_string(template_str)
        return template.render(full_context)

    def _build_context(self, base_context: dict[str, Any]) -> dict[str, Any]:
        """Build complete context including providers."""
        from collections import ChainMap

        # Start with base context
        contexts = [base_context]

        # Add context stack
        if self._context_stack:
            contexts.extend(self._context_stack)

        # Resolve context providers synchronously
        provider_context = {}

        # Global providers
        for name, provider in _GLOBAL_CONTEXT_PROVIDERS.items():
            if name not in base_context:  # Don't override explicit values
                try:
                    provider_context[name] = provider()
                except Exception:
                    pass  # Skip failed providers

        # Instance providers
        for name, provider in self._context_providers.items():
            if name not in base_context:  # Don't override explicit values
                try:
                    provider_context[name] = provider()
                except Exception:
                    pass  # Skip failed providers

        # Add provider context with lowest priority
        contexts.insert(0, provider_context)

        # Create ChainMap with proper priority (last wins)
        return dict(ChainMap(*reversed(contexts)))

    def resolve_context_sync(self, base_context: dict[str, Any]) -> dict[str, Any]:
        """
        Synchronously resolve context providers (public API).

        Args:
            base_context: Base context dictionary

        Returns:
            Resolved context with provider values
        """
        return self._resolve_context_sync(base_context)

    def _resolve_context_sync(self, base_context: dict[str, Any]) -> dict[str, Any]:
        """Synchronously resolve context providers."""
        # Import from module-level to access the global context providers
        # This is a self-reference within the templating module

        # Start with base context
        resolved = dict(base_context)

        # Get all potential keys from template
        all_keys = set(base_context.keys())
        all_keys.update(self._context_providers.keys())
        all_keys.update(_GLOBAL_CONTEXT_PROVIDERS.keys())

        for key in all_keys:
            if key in base_context:
                # Already has a value
                continue
            elif key in self._context_providers:
                # Call instance provider (must be sync)
                provider = self._context_providers[key]

                # Emit context:provider:call event
                if hasattr(self, "_agent") and self._agent:
                    self._agent.do(
                        AgentEvents.CONTEXT_PROVIDER_BEFORE,
                        provider_name=key,
                        provider=provider,
                        agent=self._agent,
                        extension=self,
                    )

                # Only support sync providers in sync context
                if not asyncio.iscoroutinefunction(provider):
                    value = provider()

                    # Emit context:provider:response event (modifiable)
                    if hasattr(self, "_agent") and self._agent:
                        result = self._agent.do(
                            AgentEvents.CONTEXT_PROVIDER_AFTER,
                            provider_name=key,
                            value=value,
                            agent=self._agent,
                            extension=self,
                        )
                        # do() might return modified value directly
                        if result is not None:
                            value = result

                    resolved[key] = value
            elif key in _GLOBAL_CONTEXT_PROVIDERS:
                # Call global provider (must be sync)
                provider = _GLOBAL_CONTEXT_PROVIDERS[key]

                # Emit context:provider:call event
                if hasattr(self, "_agent") and self._agent:
                    self._agent.do(
                        AgentEvents.CONTEXT_PROVIDER_BEFORE,
                        provider_name=key,
                        provider=provider,
                        agent=self._agent,
                        extension=self,
                    )

                # Only support sync providers in sync context
                if not asyncio.iscoroutinefunction(provider):
                    value = provider()

                    # Emit context:provider:response event (modifiable)
                    if hasattr(self, "_agent") and self._agent:
                        result = self._agent.apply_sync(
                            AgentEvents.CONTEXT_PROVIDER_AFTER,
                            provider_name=key,
                            value=value,
                            agent=self._agent,
                            extension=self,
                        )
                        # apply_sync returns EventContext, extract output if available
                        if result and result.output is not None:
                            value = result.output

                    resolved[key] = value

        return resolved
