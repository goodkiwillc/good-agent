import pytest

from good_agent.core.templates import render_template, render_template_async


def test_render_template_renders_with_context():
    template = "Hello {{ name }}"
    assert render_template(template, {"name": "World"}) == "Hello World"


def test_render_template_returns_original_on_error():
    template = "Value {{ missing }}"
    assert render_template(template, {}) == template


@pytest.mark.asyncio
async def test_render_template_async_renders_values():
    template = "Async {{ noun }}"
    result = await render_template_async(template, {"noun": "Success"})
    assert result == "Async Success"


@pytest.mark.asyncio
async def test_render_template_async_returns_original_on_error():
    template = "{{ missing_value }}"
    result = await render_template_async(template, {})
    assert result == template
