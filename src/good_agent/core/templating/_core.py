import inspect
import typing
import warnings
from abc import ABC, abstractmethod
from collections import ChainMap
from typing import Any

from jinja2 import BaseLoader, Environment
from jinja2 import (
    pass_context as _pass_context,
)
from jinja2 import (
    pass_environment as _pass_environment,
)
from jinja2 import (
    pass_eval_context as _pass_eval_context,
)
from jinja2.nodes import EvalContext
from jinja2.runtime import Context


def _extract_template(cls):
    return inspect.cleandoc(cls.__template__).strip() if cls.__template__ else inspect.getdoc(cls)


class AbstractTemplate(ABC):
    """PURPOSE: Base class for renderable templates.

    ROLE: Enables projects to define templates via class-based patterns while supporting
    inheritance of template strings and configuration.

    LIFECYCLE: Subclass → optionally set class variable __template__ or implement render()
    → instantiate → call render() or str(instance).

    EXTENSION POINTS: Override render(); provide __template_config__ via subclassing to
    influence environment creation upstream.
    """

    __template__: typing.ClassVar[str | None] = None
    __template_config__: typing.ClassVar[ChainMap] = ChainMap()

    def __init_subclass__(cls, template_config: dict | None = None, **kwargs):
        super().__init_subclass__()

        # Get the existing template config or create a new one
        base_config: ChainMap[str, Any] = getattr(cls, "__template_config__", ChainMap())
        if not isinstance(base_config, ChainMap):
            base_config = ChainMap(base_config if base_config else {})

        # Only add a new layer when an explicit template_config is provided; otherwise preserve inherited layers
        if template_config is not None:
            cls.__template_config__ = base_config.new_child(template_config)
        else:
            cls.__template_config__ = base_config

    def get_template(self) -> str:
        if current_template := _extract_template(self):
            return current_template
        else:
            for base in self.__class__.__bases__:
                if template := _extract_template(base):
                    return template

        raise ValueError("No template found")

    @abstractmethod
    def render(self, *args, **kwargs):
        """Render the template with the given arguments.

        Returns:
            str: Rendered template output.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def __str__(self):
        """
        Return the string representation of the template.
        """
        return self.render()

    def __iadd__(self, other):
        if isinstance(other, str):
            return self.render() + other
        if isinstance(other, AbstractTemplate):
            return self.render() + other.render()
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, str):
            return self.render() + other
        if isinstance(other, AbstractTemplate):
            return self.render() + other.render()
        return NotImplemented


def _deprecated_filter(func):
    """Mark a registered filter/function as deprecated, emitting a warning at call time."""

    def wrapper(*args, **kwargs):
        warnings.warn(
            f"Filter '{func.__name__}' is deprecated and will be removed in future versions.",
            DeprecationWarning,
            stacklevel=2,
        )
        return func(*args, **kwargs)

    return wrapper


class TemplateDependencyRegistry:
    """Registry for Jinja filters and global functions with optional context passing.

    RESPONSIBILITIES:
    - Register callables as Jinja filters/globals, with pass_context/eval/env support
    - Support deprecated aliases that emit warnings but keep backwards compatibility
    - Apply all registrations to a provided Environment
    """

    def __init__(self):
        self.filters = {}
        self.functions = {}

    def register_filter(
        self,
        name: str,
        deprecated_aliases: list[str] | None = None,
        pass_context: None | typing.Literal[True, "eval", "env"] = None,
    ):
        def decorator(func):
            if pass_context is True:
                func = _pass_context(func)
            elif pass_context == "eval":
                func = _pass_eval_context(func)
            elif pass_context == "env":
                func = _pass_environment(func)
            if not callable(func):
                raise TypeError(f"Filter function must be callable, got {type(func).__name__}")
            # Register primary name
            self.filters[name] = func
            # Register deprecated aliases as wrappers that emit a warning
            if deprecated_aliases:
                for alias in deprecated_aliases:
                    if alias in self.filters:
                        raise ValueError(
                            f"Filter name '{alias}' is already registered. "
                            "Please choose a different name."
                        )
                    self.filters[alias] = _deprecated_filter(func)
            return func

        return decorator

    def get_filters(self):
        return self.filters

    def register_function(
        self,
        name: str,
        deprecated_aliases: list[str] | None = None,
        pass_context: typing.Literal[True, False, "eval", "env"] = False,
    ):
        def decorator(func):
            if pass_context is True:
                func = _pass_context(func)
            elif pass_context == "eval":
                func = _pass_eval_context(func)
            elif pass_context == "env":
                func = _pass_environment(func)
            if not callable(func):
                raise TypeError(f"Function must be callable, got {type(func).__name__}")
            # Register primary name
            self.functions[name] = func
            # Register deprecated aliases as wrappers that emit a warning
            if deprecated_aliases:
                for alias in deprecated_aliases:
                    if alias in self.functions:
                        raise ValueError(
                            f"Function name '{alias}' is already registered. "
                            "Please choose a different name."
                        )
                    self.functions[alias] = _deprecated_filter(func)
            return func

        return decorator

    def apply(self, env: Environment):
        """Apply all registered filters/functions to the given Jinja2 environment."""
        for name, func in self.filters.items():
            env.filters[name] = func
        for name, func in self.functions.items():
            if name in env.globals:
                raise ValueError(
                    f"Function name '{name}' is already registered. Please choose a different name."
                )
            env.globals[name] = func


TEMPLATE_DEPENDENCIES = TemplateDependencyRegistry()

register_filter = TEMPLATE_DEPENDENCIES.register_filter
register_function = TEMPLATE_DEPENDENCIES.register_function


def _compose_environment(
    *configs: dict,
    loader: BaseLoader | None = None,
    env_cls: type[Environment] = Environment,
):
    """Create a Jinja2 Environment from layered configs and the global dependency registry.

    - Merges provided config dicts left→right (later override earlier) with extension
      lists de-duplicated while preserving order.
    - Applies all registered filters/functions from TEMPLATE_DEPENDENCIES.

    Args:
        *configs: Environment config dictionaries to layer (later override earlier).
        loader: Optional Jinja2 loader to use.
        env_cls: Environment class to instantiate (defaults to jinja2.Environment).
                 Allows callers to provide SandboxedEnvironment-compatible classes.
    """
    all_extensions = []
    for config in configs:
        if "extensions" in config:
            extensions = config.get("extensions", [])
            all_extensions.extend(extensions)

    if all_extensions:
        # Remove duplicates while preserving order
        all_extensions = list(dict.fromkeys(all_extensions))
        configs = (*configs, {"extensions": all_extensions})

    # Reverse configs so later ones override earlier ones
    env = env_cls(loader=loader, **ChainMap(*reversed(configs)))

    TEMPLATE_DEPENDENCIES.apply(env)

    return env


__all__ = [
    "AbstractTemplate",
    "register_filter",
    "register_function",
    "Context",
    "EvalContext",
]
