import inspect
import logging
import os
from collections import ChainMap
from collections.abc import Callable
from datetime import UTC
from pathlib import Path
from typing import TYPE_CHECKING, Any

from jinja2 import ChoiceLoader

from good_agent.core import templating
from good_agent.core.components import AgentComponent
from good_agent.events import AgentEvents
from good_agent.extensions.template_manager.injection import (
    ContextResolver,
    _modify_function_for_injection,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    pass


# Global context providers registry
_GLOBAL_CONTEXT_PROVIDERS: dict[str, Callable[[], Any]] = {}


def global_context_provider(name: str):
    """Register a global context provider.

    Args:
        name: Name of the context provider

    Warning:
        Emits a warning if overwriting an existing context provider.
    """
    import warnings

    def decorator(func: Callable[[], Any]) -> Callable[[], Any]:
        if name in _GLOBAL_CONTEXT_PROVIDERS:
            existing_func = _GLOBAL_CONTEXT_PROVIDERS[name]
            warnings.warn(
                f"Overwriting existing global context provider '{name}' "
                f"(was: {existing_func.__module__}.{existing_func.__name__}, "
                f"now: {func.__module__}.{func.__name__})",
                UserWarning,
                stacklevel=3,
            )
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
        from good_common.utilities import now_pt  # type: ignore[import-untyped]

        now = now_pt()
        # Return datetime at midnight for consistency
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    except ImportError:
        # Fall back to UTC if good_common is not available
        from datetime import datetime

        now = datetime.now(UTC)
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
        from good_common.utilities import now_pt  # type: ignore[import-untyped]

        return now_pt()
    except ImportError:
        # Fall back to UTC if good_common is not available
        from datetime import datetime

        return datetime.now(UTC)


def find_prompts_directory() -> Path | None:
    """Find the prompts directory from env override or by looking for prompts.yaml."""
    env_dir = os.getenv("GOOD_AGENT_PROMPTS_DIR")
    logger.info("Searching for prompts directory...")
    if env_dir:
        env_path = Path(env_dir).expanduser()
        logger.info(f"Using prompts directory from GOOD_AGENT_PROMPTS_DIR: {env_path}")
        if env_path.exists():
            return env_path

    current = Path.cwd()

    logger.info(current)

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
    """Deferred Jinja snippet that renders once context becomes available.

    Useful for tool parameters or message assembly where values are resolved later.
    See ``examples/templates/render_template.py`` for inline and cached rendering
    patterns.
    """

    def __init__(self, template: str, strict: bool = False):
        """Store a template string and error-handling preference."""
        self.template = template
        self.strict = strict
        self._rendered: str | None = None

    def render(self, context: dict[str, Any]) -> str:
        """Render with the provided context, caching the last successful output.

        First renders go through the templating engine (~1-10ms) while cached
        renders return immediately (<1ms). In non-strict mode missing variables
        fall back to the original template string. See
        ``examples/templates/render_template.py`` for full usage.
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
        """Return cached render if available, otherwise the template string."""
        return self._rendered if self._rendered else self.template

    def __repr__(self) -> str:
        """Return a debug representation including template text and strict flag."""
        return f"Template({self.template!r}, strict={self.strict})"


class TemplateManager(AgentComponent):
    """Agent component that renders inline, registry, or file templates.

    It layers global/context-provider data, exposes sync helpers, and fires
    AgentEvents around render operations. ``examples/templates/render_template.py``
    shows basic inline usage without relying on file discovery.
    """

    def __init__(
        self,
        prompts_dir: Path | None = None,
        enable_file_templates: bool = True,
        use_sandbox: bool = True,
    ):
        """Configure prompt directories, file access, and sandboxing behavior."""
        super().__init__()  # Initialize AgentComponent/EventRouter
        self._explicit_prompts_dir = prompts_dir
        self._context_providers: dict[str, Callable[[], Any]] = {}
        self._context_stack: list[dict[str, Any]] = []
        self.use_sandbox = use_sandbox

        logger.info(
            f"Initializing TemplateManager with file templates "
            f"{'enabled' if enable_file_templates else 'disabled'}."
        )

        # Initialize context resolver
        self._context_resolver = ContextResolver(self)

        # File template support
        self.file_storage: Any = None  # ChainedStorage | FileSystemStorage | None
        self.file_loader: Any = None  # StorageTemplateLoader | None
        self.file_templates_enabled = enable_file_templates
        self._template_cache: dict[str, Any] = {}

        # Create a local registry with the global registry as parent
        self._registry = templating.TemplateRegistry(parent=templating.TEMPLATE_REGISTRY)

        # Set up the environment
        if enable_file_templates:
            self._setup_file_templates(prompts_dir)
        else:
            # Basic environment without file support
            self._env = templating.create_environment(
                config={"trim_blocks": False},
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
        state["registry_maps"] = [dict(mapping) for mapping in self._registry.templates.maps]
        return state

    def _import_state(self, state: dict[str, Any]) -> None:
        super()._import_state(state)
        self._context_providers = dict(state.get("context_providers", {}))
        self._context_stack = [dict(ctx) for ctx in state.get("context_stack", [])]
        self._template_cache = dict(state.get("template_cache", {}))
        registry_maps = state.get("registry_maps")
        if registry_maps is not None:
            from collections import ChainMap

            self._registry._templates = ChainMap(*[dict(mapping) for mapping in registry_maps])

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

            for _param_name, param in sig.parameters.items():
                if param.annotation == inspect.Parameter.empty:
                    continue
                # Check for Agent type without Depends
                param_type = str(param.annotation)
                if "Agent" in param_type and param.default == inspect.Parameter.empty:
                    needs_agent = True
                elif "Message" in param_type and param.default == inspect.Parameter.empty:
                    needs_message = True

            if needs_agent or needs_message:

                @functools.wraps(func)
                async def agent_wrapper(*args, **kwargs):
                    # Inject agent and message if needed
                    if needs_agent and "agent" not in kwargs and hasattr(self, "_agent"):
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
                    if inspect.iscoroutinefunction(func):
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
        from good_agent.extensions.template_manager.storage import (
            ChainedStorage,
            FileSystemStorage,
            StorageTemplateLoader,
        )

        logger.info("Setting up file-based template loading...")

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
            self._env = templating.create_environment(
                config={"trim_blocks": False},
                loader=combined_loader,
                use_sandbox=self.use_sandbox,
            )
        else:
            # No file sources found, use basic environment
            self._env = templating.create_environment(
                config={"trim_blocks": False},
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

        try:
            # Use a sandboxed environment for parsing (safe by default)
            env = templating.create_environment(use_sandbox=True)
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
        provider_keys: set[str] = set()
        provider_keys.update(_GLOBAL_CONTEXT_PROVIDERS.keys())
        provider_keys.update(self._context_providers.keys())

        # Resolve each provider with dependency injection
        for key in provider_keys:
            if key not in resolved_base:
                try:
                    value = await self._context_resolver.resolve_value(key, resolved_base)
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
            result = templating.render_template(template, resolved_context, environment=self._env)
        except Exception:
            # Re-raise template errors to make them fatal
            raise

        # Fire event if agent is available
        if hasattr(self, "_agent") and self._agent:
            modified_result = self._agent.events.apply_sync(
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
        """Render a string template after layering provider context values."""
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
                if not inspect.iscoroutinefunction(provider):
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
                if not inspect.iscoroutinefunction(provider):
                    value = provider()

                    # Emit context:provider:response event (modifiable)
                    if hasattr(self, "_agent") and self._agent:
                        result = self._agent.events.apply_sync(
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
