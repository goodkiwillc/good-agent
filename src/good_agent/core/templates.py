from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined


def render_template(
    template: str,
    context: dict[str, Any],
    **kwargs,
) -> str:
    try:
        env = Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
            loader=BaseLoader(),
        )
        return env.from_string(template).render(context, **kwargs)
    except Exception:
        return template


async def render_template_async(
    template: str,
    context: dict[str, Any],
    **kwargs,
) -> str:
    try:
        env = Environment(
            trim_blocks=True,
            lstrip_blocks=True,
            keep_trailing_newline=True,
            undefined=StrictUndefined,
            loader=BaseLoader(),
            enable_async=True,
        )
        return env.from_string(template).render(context, **kwargs)
    except Exception:
        return template
