import datetime
import inspect
import logging
from collections import ChainMap
from collections.abc import Callable
from typing import Any

from good_common.utilities import filter_nulls
from jinja2 import BaseLoader, Environment, TemplateNotFound, TemplateSyntaxError
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup

from good_agent.core.templating import _extensions as extensions
from good_agent.core.templating._core import (
    AbstractTemplate,
    Context,
    _compose_environment,
    register_filter,
    register_function,
)

logger = logging.getLogger(__name__)


def _get_template(cls):
    return inspect.cleandoc(cls.__template__).strip() if cls.__template__ else inspect.getdoc(cls)


DEFAULT_CONFIG = {
    "autoescape": False,
    "trim_blocks": True,
    "lstrip_blocks": True,
    "keep_trailing_newline": False,
    "line_statement_prefix": "!#",
    "line_comment_prefix": "!##",
    "extensions": [getattr(extensions, ext) for ext in extensions.__all__],
}

TemplateLike = str | bytes | Markup | AbstractTemplate


class TemplateRegistry(BaseLoader):
    """Layered, optionally singleton template loader backed by ChainMap.

    PURPOSE: Store and resolve named templates with scoping via new_context()/reset().
    - Global singleton available via TEMPLATE_REGISTRY when constructed without args
    - Supports parent chaining for hierarchical registries
    - Implements Jinja BaseLoader API (get_source, list_templates)
    """

    __instance__ = None

    def __new__(cls, *args, **kwargs):
        # Only use singleton for the global registry (when no args/kwargs)
        if not args and not kwargs and not cls.__instance__:
            cls.__instance__ = super().__new__(cls)
            return cls.__instance__
        elif not args and not kwargs and cls.__instance__:
            return cls.__instance__
        else:
            # Create new instance for non-global registries
            return super().__new__(cls)

    def __init__(self, *mappings, parent: TemplateRegistry | None = None):
        # Avoid re-initializing singleton instance
        # Use getattr with default to be type-safe
        if getattr(self, "_initialized", False):
            return

        self._parent = parent
        self._templates: ChainMap[str, Any] = ChainMap(*mappings)
        self._initialized = True

    def new_context(self, mapping: dict[str, str] | None = None):
        self._templates = self._templates.new_child(mapping)
        return self

    def add_template(self, name: str, template: TemplateLike, replace: bool = False):
        if name in self._templates and not replace:
            raise ValueError(f"Template {name} already exists")
        self._templates[name] = template
        return self

    def reset(self):
        self._templates = self._templates.parents
        return self

    def __enter__(self, mapping):
        return self.new_context(mapping)

    def __exit__(self, exc_type, exc_value, traceback):
        self.reset()
        # return False

    @property
    def templates(self):
        return self._templates

    def get_source(
        self,
        environment: Environment,
        template: str,
    ) -> tuple[str, None, Callable[[], bool]]:
        if template in self.templates:
            source = self.templates[template]
            return source, None, lambda: source == self.templates.get(template)

        # Try parent registry if we have one
        if self._parent is not None:
            try:
                return self._parent.get_source(environment, template)
            except TemplateNotFound:
                pass

        raise TemplateNotFound(template)

    def list_templates(self) -> list[str]:
        # Combine local and parent template names
        names = set(self.templates.keys())
        if self._parent is not None:
            names.update(self._parent.list_templates())
        return sorted(names)

    def get_template(self, name: str) -> str:
        try:
            return self.templates[name]
        except KeyError:
            # Try parent registry if we have one
            if self._parent is not None:
                try:
                    return self._parent.get_template(name)
                except TemplateNotFound:
                    pass
            raise TemplateNotFound(name) from None

    def get_template_names(self) -> list[str]:
        # Combine local and parent template names
        names = set(self.templates.keys())
        if self._parent is not None:
            names.update(self._parent.get_template_names())
        return sorted(names)

    def __getitem__(self, name: str) -> str:
        try:
            return self.templates[name]
        except KeyError:
            # Try parent registry if we have one
            if self._parent is not None:
                try:
                    return self._parent[name]
                except TemplateNotFound:
                    pass
            raise TemplateNotFound(name) from None


TEMPLATE_REGISTRY = TemplateRegistry()


def add_named_template(
    name: str,
    template: TemplateLike,
    replace: bool = False,
    append_newline: bool = False,
):
    from good_agent.core.text import string

    """Add a named template to the global registry with optional newline and replace.

    Args:
        name: Registry key.
        template: Template source (str/bytes/Markup/AbstractTemplate).
        replace: Overwrite existing entry if True.
        append_newline: Ensure trailing newline on string templates if missing.
    """
    if isinstance(template, bytes):
        template = template.decode("utf-8")

    if isinstance(template, str):
        template = string.unindent(template)
        if append_newline and not template.endswith("\n"):
            template += "\n"
    return TEMPLATE_REGISTRY.add_template(name, template, replace=replace)


def get_named_template(name: str) -> str:
    """Get a named template from the global registry or raise TemplateNotFound."""
    return TEMPLATE_REGISTRY.get_template(name)


def create_environment(
    config: dict | None = None,
    loader: BaseLoader | None = None,
    *,
    use_sandbox: bool = False,
    additional_globals: dict[str, Any] | None = None,
    additional_filters: dict[str, Any] | None = None,
    additional_tests: dict[str, Any] | None = None,
):
    """Create a Jinja2 Environment using DEFAULT_CONFIG overlaid with optional config/loader.

    Args:
        config: Optional environment configuration to overlay on defaults.
        loader: Optional loader; defaults to the global TEMPLATE_REGISTRY.
        use_sandbox: When True, creates a SandboxedEnvironment with stricter getattr rules.
        additional_globals: Extra globals to inject into the environment.
        additional_filters: Extra filters to inject into the environment.
        additional_tests: Extra tests to inject into the environment.
    """

    env_cls: type[Environment]
    if use_sandbox:
        # Define a stricter sandbox class that blocks dangerous attribute access
        class StrictSandboxedEnvironment(SandboxedEnvironment):
            def getattr(self, obj, attribute):
                # Block most dunder attributes except safe protocol methods
                if attribute.startswith("__"):
                    if attribute not in (
                        "__iter__",
                        "__len__",
                        "__getitem__",
                        "__str__",
                        "__repr__",
                        "__bool__",
                    ):
                        raise AttributeError(f"Access to attribute '{attribute}' is blocked")

                # Block access to function/method internals and frames
                if attribute in (
                    "func_globals",
                    "func_code",
                    "func_closure",
                    "im_class",
                    "im_func",
                    "im_self",
                    "gi_code",
                    "gi_frame",
                    "gi_running",
                    "f_locals",
                    "f_globals",
                    "f_code",
                    "f_back",
                    "__globals__",
                    "__code__",
                    "__closure__",
                ):
                    raise AttributeError(f"Access to attribute '{attribute}' is blocked")

                return super().getattr(obj, attribute)

        env_cls = StrictSandboxedEnvironment
    else:
        env_cls = Environment

    env: Environment = _compose_environment(
        DEFAULT_CONFIG,
        config or {},
        loader=loader or TEMPLATE_REGISTRY,
        env_cls=env_cls,
    )

    # Add safe builtins and any additional items for sandboxed environments
    if use_sandbox:
        safe_builtins = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "tuple": tuple,
            "set": set,
            "len": len,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,
            "reversed": reversed,
            "sorted": sorted,
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "round": round,
            "divmod": divmod,
            "chr": chr,
            "ord": ord,
            "format": format,
        }
        env.globals.update(safe_builtins)

    if additional_globals:
        env.globals.update(additional_globals)
    if additional_filters:
        env.filters.update(additional_filters)
    if additional_tests:
        env.tests.update(additional_tests)

    return env


@register_filter("render", pass_context=True)
def _render_template(
    context: Context,
    template: AbstractTemplate,
    **kwargs: dict[str, str | None],
):
    return template.render(**filter_nulls(kwargs))


@register_function("now", pass_context=True)
def now(environment: Environment, tz: str = "US/Pacific") -> datetime.datetime:
    """Return timezone-aware current datetime.

    Args:
        environment: Jinja2 environment (provided via pass_context, unused).
        tz: IANA timezone name.
    """
    from good_common.utilities import now_tz

    return now_tz(tz)


def render_template(
    template: TemplateLike,
    context: dict[str, Any] | None = None,
    environment: Environment | None = None,
    environment_config: dict | None = None,
    environment_loader: BaseLoader | None = None,
    auto_dedent: bool = True,
    **config,
):
    """
    Render a template (string, bytes, Markup, or AbstractTemplate) with context.

    By default, environment includes Sections extension:
    ```python
    t = render_template(
        '''
        !# section tag key=value
        {{ test}}
        !# end section
        ''',
        context={"test": "This is a test", "value": "example"},
    )
    assert t == '''
    <tag key="example">
        This is a test
    </tag>
    ```

    """
    try:
        context = context or {}
        env = environment or create_environment(
            config=environment_config,
            loader=environment_loader,
        )
        if isinstance(template, bytes):
            template = template.decode("utf-8")

        if auto_dedent and isinstance(template, str):
            import inspect

            template = inspect.cleandoc(template).strip()

        if isinstance(template, AbstractTemplate):
            return template.render(**filter_nulls(context))
        elif isinstance(template, str):
            _template = env.from_string(template)
            return _template.render(**filter_nulls(context))
        else:
            raise TypeError(f"Template must be a string or AbstractTemplate, got {type(template)}")
    except Exception as e:
        # Build detailed error message
        error_parts = [f"Error rendering template: {e}"]

        # Check for common section tag errors
        if isinstance(e, TemplateSyntaxError) and "expected token" in str(e):
            # Try to detect section tag issues
            if isinstance(template, str):
                import re

                # Check for unquoted section names with special chars
                section_pattern = r"{%\s*section\s+([a-zA-Z_][a-zA-Z0-9_-]+)\s*%}|!#\s*section\s+([a-zA-Z_][a-zA-Z0-9_-]+)"
                matches = re.findall(section_pattern, template)
                for match in matches:
                    name = match[0] or match[1]
                    if "-" in name or not name.replace("_", "").replace("-", "").isalnum():
                        error_parts.append(
                            f"\nHint: Section name '{name}' contains special characters."
                        )
                        error_parts.append(
                            f"      Use quotes: {{% section '{name}' %}} or !# section '{name}'"
                        )
                        break

        # Add location information if available (for TemplateSyntaxError)
        # Direct type check for Jinja2 exceptions instead of Protocol
        if isinstance(e, TemplateSyntaxError):
            if e.lineno:
                error_parts.append(f"Line: {e.lineno}")
            if e.name:
                error_parts.append(f"Template: {e.name}")
            if e.filename:
                error_parts.append(f"File: {e.filename}")
        elif hasattr(e, "__class__") and e.__class__.__name__ == "TemplateSyntaxError":
            # Fallback for cases where the exception might be from a different jinja2 version
            lineno = getattr(e, "lineno", None)
            name = getattr(e, "name", None)
            filename = getattr(e, "filename", None)
            if lineno:
                error_parts.append(f"Line: {lineno}")
            if name:
                error_parts.append(f"Template: {name}")
            if filename:
                error_parts.append(f"File: {filename}")

        # Add template source context
        if isinstance(template, str):
            template_lines = template.split("\n")
            # Check if exception has line number - direct check for Jinja2 exception
            lineno = getattr(e, "lineno", None) if isinstance(e, TemplateSyntaxError) else None
            if lineno and lineno <= len(template_lines):
                # Show the problematic line with context
                start = max(0, lineno - 2)
                end = min(len(template_lines), lineno + 1)
                error_parts.append("\nTemplate context:")
                for i in range(start, end):
                    line_num = i + 1
                    marker = ">>>" if line_num == lineno else "   "
                    error_parts.append(f"{marker} {line_num:3d}: {template_lines[i]}")
        else:
            error_parts.append(f"\nTemplate: {str(template)[:200]}")

        error_parts.append(f"\nContext keys: {list(context.keys()) if context else []}")

        error_msg = "\n".join(error_parts)

        logger.exception(error_msg)
        raise RuntimeError(error_msg) from e
