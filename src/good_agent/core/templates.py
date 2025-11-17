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
        rendered_context = {**context, **kwargs}
        return env.from_string(template).render(**rendered_context)
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
        rendered_context = {**context, **kwargs}
        template_obj = env.from_string(template)
        return await template_obj.render_async(**rendered_context)
    except Exception:
        return template
