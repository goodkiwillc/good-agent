import inspect
from collections.abc import Callable
from typing import Any


# Sentinel value for missing defaults
class _Missing:
    def __repr__(self):
        return "<MISSING>"


_MISSING = _Missing()


class _ContextValueDescriptor:
    """Internal descriptor for injecting context values into tools and context providers."""

    _MISSING = _MISSING

    def __init__(
        self,
        name: str,
        default: Any = _MISSING,
        default_factory: Callable[[], Any] | None = None,
        required: bool = True,
    ):
        """
        Initialize a context value descriptor.

        Args:
            name: Name of the context value to inject
            default: Default value if context value is not available
            default_factory: Factory function to create default value
            required: If True and no default, raise error if value missing

        Raises:
            ValueError: If both default and default_factory are specified
        """
        if default is not _MISSING and default_factory is not None:
            raise ValueError("Cannot specify both default and default_factory")

        self.name = name
        self.default = default
        self.default_factory = default_factory
        self.required = required

    def __repr__(self):
        parts = [f"name={self.name!r}"]
        if self.default is not _MISSING:
            parts.append(f"default={self.default!r}")
        if self.default_factory is not None:
            parts.append(f"default_factory={self.default_factory!r}")
        if not self.required:
            parts.append(f"required={self.required}")
        return f"_ContextValueDescriptor({', '.join(parts)})"


def ContextValue(
    name: str,
    default: Any = _MISSING,
    default_factory: Callable[[], Any] | None = None,
    required: bool = True,
) -> Any:
    """
    Factory function for creating context value descriptors.

    Returns Any to avoid type warnings while maintaining functionality.

    Args:
        name: Name of the context value to inject
        default: Default value if context value is not available
        default_factory: Factory function to create default value
        required: If True and no default, raise error if value missing

    Returns:
        _ContextValueDescriptor instance typed as Any

    Raises:
        ValueError: If both default and default_factory are specified
    """
    return _ContextValueDescriptor(name, default, default_factory, required)


# Export _MISSING sentinel for backwards compatibility with tests
# Make _MISSING accessible through ContextValue for backwards compatibility
ContextValue._MISSING = _MISSING  # type: ignore[attr-defined]


class ContextInjectionError(Exception):
    """Base exception for context injection errors."""

    pass


class CircularDependencyError(ContextInjectionError):
    """Raised when circular dependency is detected in context providers."""

    def __init__(self, chain: list[str]):
        self.chain = chain
        message = f"Circular dependency detected in context providers: {' -> '.join(chain)}"
        super().__init__(message)


class MissingContextValueError(ContextInjectionError):
    """Raised when a required context value is not available."""

    def __init__(self, name: str, available: list[str] | None = None):
        self.name = name
        self.available = available or []
        message = f"Context value '{name}' is required but not available"
        if available:
            message += f". Available values: {', '.join(available)}"
        super().__init__(message)


class ContextProviderError(ContextInjectionError):
    """Raised when a context provider fails during execution."""

    def __init__(self, provider_name: str, original_error: Exception):
        self.provider_name = provider_name
        self.original_error = original_error
        message = f"Failed to execute context provider '{provider_name}': {original_error}"
        super().__init__(message)


class ContextResolver:
    """Manages context resolution with dependency tracking."""

    def __init__(self, template_manager: Any):
        """
        Initialize the context resolver.

        Args:
            template_manager: The TemplateManager instance
        """
        self.template_manager = template_manager
        self._resolution_stack: list[str] = []  # Track resolution chain
        self._resolved_cache: dict[str, Any] = {}  # Cache resolved values

    def get_provider(self, name: str) -> Callable | None:
        """
        Get a context provider by name.

        Args:
            name: Provider name

        Returns:
            Provider function or None if not found
        """
        # Check instance providers first
        if hasattr(self.template_manager, "_context_providers"):
            if name in self.template_manager._context_providers:
                return self.template_manager._context_providers[name]

        # Check global providers
        from good_agent.extensions.template_manager.core import (
            _GLOBAL_CONTEXT_PROVIDERS,
        )

        if name in _GLOBAL_CONTEXT_PROVIDERS:
            return _GLOBAL_CONTEXT_PROVIDERS[name]

        return None

    async def call_provider_with_injection(
        self, provider: Callable, context: dict[str, Any]
    ) -> Any:
        """
        Call a provider function with dependency injection for context values.

        Args:
            provider: Provider function
            context: Current context for injection

        Returns:
            Provider result
        """
        # Check if provider needs context injection
        context_params = _get_context_params(provider)

        if context_params:
            # Provider needs context values
            kwargs = {}

            # Resolve each context dependency recursively
            for param_name, context_value in context_params.items():
                # Try to resolve the context value
                if context_value.name in context:
                    # Already resolved
                    kwargs[param_name] = context[context_value.name]
                else:
                    # Need to resolve it recursively
                    try:
                        resolved = await self.resolve_value(context_value.name, context)
                        kwargs[param_name] = resolved
                    except (KeyError, CircularDependencyError):
                        # Handle missing value
                        if context_value.default is not _MISSING:
                            kwargs[param_name] = context_value.default
                        elif context_value.default_factory is not None:
                            kwargs[param_name] = context_value.default_factory()
                        elif not context_value.required:
                            kwargs[param_name] = None
                        else:
                            raise MissingContextValueError(
                                context_value.name, list(context.keys())
                            ) from None

            # Call provider with resolved context values
            if inspect.iscoroutinefunction(provider):
                return await provider(**kwargs)
            else:
                return provider(**kwargs)
        else:
            # Simple provider without context dependencies
            if inspect.iscoroutinefunction(provider):
                return await provider()
            else:
                return provider()

    async def resolve_value(self, name: str, base_context: dict[str, Any]) -> Any:
        """
        Resolve a context value with circular dependency detection.

        Args:
            name: Context value name
            base_context: Base context dictionary

        Returns:
            Resolved value

        Raises:
            CircularDependencyError: If circular dependency detected
            KeyError: If no provider found
            ContextProviderError: If provider execution fails
        """
        # Check for circular dependency
        if name in self._resolution_stack:
            chain = self._resolution_stack + [name]
            raise CircularDependencyError(chain)

        # Check cache
        if name in self._resolved_cache:
            return self._resolved_cache[name]

        # Check if already in base context
        if name in base_context:
            return base_context[name]

        # Push to stack
        self._resolution_stack.append(name)

        try:
            # Get provider
            provider = self.get_provider(name)
            if not provider:
                raise KeyError(f"No context provider for '{name}'")

            # Build context for this provider with what we have so far
            current_context = dict(base_context)
            current_context.update(self._resolved_cache)

            # Execute provider with error handling and context injection
            try:
                value = await self.call_provider_with_injection(provider, current_context)
            except CircularDependencyError:
                # Re-raise circular dependency errors without wrapping
                raise
            except MissingContextValueError:
                # Re-raise missing context value errors
                raise
            except Exception as e:
                raise ContextProviderError(name, e) from e

            # Cache result
            self._resolved_cache[name] = value

            return value

        finally:
            # Pop from stack
            self._resolution_stack.pop()

    async def resolve_all(self, base_context: dict[str, Any]) -> dict[str, Any]:
        """
        Resolve all context values.

        Args:
            base_context: Base context dictionary

        Returns:
            Complete resolved context
        """
        resolved = dict(base_context)

        # Get all provider names
        provider_names = set()
        if hasattr(self.template_manager, "_context_providers"):
            provider_names.update(self.template_manager._context_providers.keys())

        from good_agent.extensions.template_manager.core import (
            _GLOBAL_CONTEXT_PROVIDERS,
        )

        provider_names.update(_GLOBAL_CONTEXT_PROVIDERS.keys())

        # Resolve each provider
        for name in provider_names:
            if name not in resolved:
                try:
                    resolved[name] = await self.resolve_value(name, base_context)
                except Exception:
                    # Skip failed providers for now
                    pass

        return resolved

    def clear_cache(self):
        """Clear the resolution cache."""
        self._resolved_cache.clear()
        self._resolution_stack.clear()


def _get_context_params(func: Callable) -> dict[str, _ContextValueDescriptor]:
    """
    Extract ContextValue parameters from a function.

    Args:
        func: Function to inspect

    Returns:
        Dictionary mapping parameter names to _ContextValueDescriptor instances
    """
    sig = inspect.signature(func)
    context_params = {}

    for name, param in sig.parameters.items():
        if isinstance(param.default, _ContextValueDescriptor):
            context_params[name] = param.default

    return context_params


def _get_injection_params(
    func: Callable,
) -> tuple[dict[str, Any], dict[str, _ContextValueDescriptor]]:
    """
    Extract both Depends and ContextValue parameters from a function.

    Args:
        func: Function to inspect

    Returns:
        Tuple of (depends_params, context_params) dictionaries
    """
    sig = inspect.signature(func)
    depends_params = {}
    context_params = {}

    for name, param in sig.parameters.items():
        if isinstance(param.default, _ContextValueDescriptor):
            context_params[name] = param.default
        elif param.default != inspect.Parameter.empty:
            # Robustly detect fast_depends.Depends without importing at module import time
            is_depends = False
            try:
                from fast_depends import Depends as _FDDepends  # type: ignore[import-untyped]

                if isinstance(param.default, _FDDepends):  # type: ignore[arg-type]
                    is_depends = True
            except Exception:
                pass
            # Additional heuristics for different versions/implementations
            if not is_depends:
                t = type(param.default)
                type_name = getattr(t, "__name__", "")
                mod = getattr(t, "__module__", "")
                if type_name in {"Depends", "Dependant"}:
                    is_depends = True
                elif mod.startswith("fast_depends") or mod.startswith("di"):
                    is_depends = type_name.lower().startswith("depend")

            if is_depends:
                depends_params[name] = param.default

    return depends_params, context_params


def _modify_function_for_injection(func: Callable) -> Callable:
    """
    Modify function to support both Depends and ContextValue injection.

    This function wraps a context provider to inject dependencies.

    Args:
        func: Function to modify

    Returns:
        Modified function with injection support
    """
    import functools

    from fast_depends import inject

    sig = inspect.signature(func)
    context_params = _get_context_params(func)

    # Check if there are any Depends parameters
    has_depends = False
    for param in sig.parameters.values():
        if param.default != inspect.Parameter.empty:
            if type(param.default).__name__ == "Depends":
                has_depends = True
                break

    if not context_params and not has_depends:
        return func  # No injection needed

    # If there are Depends parameters, apply fast_depends injection
    if has_depends:
        func = inject(func)

    # If there are context parameters, wrap to handle them
    if context_params:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Check if 'agent' and 'message' are in kwargs (for context providers)
            # These would be passed by the resolver
            kwargs.get("agent")
            kwargs.get("message")
            context = kwargs.get("_context", {})

            # Inject context values
            for param_name, context_value in context_params.items():
                if param_name not in kwargs:
                    # Try to get from context
                    if context_value.name in context:
                        kwargs[param_name] = context[context_value.name]
                    elif context_value.default is not _MISSING:
                        kwargs[param_name] = context_value.default
                    elif context_value.default_factory is not None:
                        kwargs[param_name] = context_value.default_factory()
                    elif not context_value.required:
                        kwargs[param_name] = None
                    else:
                        raise MissingContextValueError(
                            context_value.name, list(context.keys()) if context else []
                        )

            # Remove internal context parameter
            kwargs.pop("_context", None)

            # Call original function
            if inspect.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        return wrapper

    return func
