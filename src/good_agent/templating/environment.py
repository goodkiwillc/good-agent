from collections.abc import Callable
from typing import Any

from jinja2 import Environment
from jinja2 import select_autoescape as _select_autoescape

from good_agent.core import templating as _core_templating


def create_template_environment(
    use_sandbox: bool = True,
    autoescape: bool | list[str] = False,
    max_string_length: int | None = 100000,
    additional_globals: dict[str, Any] | None = None,
    additional_filters: dict[str, Callable] | None = None,
    additional_tests: dict[str, Callable] | None = None,
    extensions: list[type] | None = None,
    loader=None,
    **kwargs: Any,
) -> Environment:
    """Create a Jinja2 environment via good_agent.templating.create_environment.

    Parameters mirror the previous agent-specific factory but are forwarded to the
    core implementation to avoid duplication.
    """
    # Build config for the core environment
    config = dict(kwargs)
    if isinstance(autoescape, list):
        config["autoescape"] = _select_autoescape(autoescape)
    elif autoescape is True:
        config["autoescape"] = _select_autoescape(["html", "xml"])
    elif autoescape is False:
        config["autoescape"] = False

    if extensions:
        config["extensions"] = extensions

    env = _core_templating.create_environment(
        config=config,
        loader=loader,
        use_sandbox=use_sandbox,
        additional_globals=additional_globals,
        additional_filters=additional_filters,
        additional_tests=additional_tests,
    )
    return env


def create_simple_template_environment(
    use_sandbox: bool = True,
) -> Environment:
    """Create a simple environment using the core templating factory."""
    return create_template_environment(use_sandbox=use_sandbox)


# Singleton instances for common use cases
_default_sandbox_env: Environment | None = None
_default_unsafe_env: Environment | None = None


def get_default_environment(
    use_sandbox: bool = True,
) -> Environment:
    """Get a cached default environment instance built via core templating."""
    global _default_sandbox_env, _default_unsafe_env

    if use_sandbox:
        if _default_sandbox_env is None:
            _default_sandbox_env = create_template_environment(use_sandbox=True)
        return _default_sandbox_env
    else:
        if _default_unsafe_env is None:
            _default_unsafe_env = create_template_environment(use_sandbox=False)
        return _default_unsafe_env
