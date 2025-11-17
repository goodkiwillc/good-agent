from __future__ import annotations

from good_agent.content import RenderMode, TemplateContentPart, TextContentPart
from good_agent.messages import Message, UserMessage
from good_agent.messages.base import _get_render_stack


class DummyLLMContent:
    def __llm__(self) -> str:  # pragma: no cover - exercised via protocol call
        return "llm-view"


def test_create_content_part_from_nested_message() -> None:
    inner = UserMessage("first", "second")

    part = Message._create_content_part(inner)

    assert isinstance(part, TextContentPart)
    assert part.text == "first\nsecond"


def test_create_content_part_from_llm_protocol() -> None:
    part = Message._create_content_part(DummyLLMContent())

    assert isinstance(part, TextContentPart)
    assert part.text == "llm-view"


def test_create_content_part_detects_templates() -> None:
    part = Message._create_content_part("{{ name }}", template_detection=True)

    assert isinstance(part, TemplateContentPart)
    assert part.template == "{{ name }}"


def test_render_recursion_uses_cache() -> None:
    message = UserMessage("cached")
    message._rendered_cache[RenderMode.DISPLAY] = "cached"

    render_key = f"{id(message)}:{RenderMode.DISPLAY.value}"
    stack = _get_render_stack()
    stack.add(render_key)

    try:
        assert message.render(RenderMode.DISPLAY) == "cached"
    finally:
        stack.discard(render_key)


def test_render_recursion_without_cache_returns_fallback() -> None:
    message = UserMessage("value")
    render_key = f"{id(message)}:{RenderMode.DISPLAY.value}"
    stack = _get_render_stack()
    stack.add(render_key)

    try:
        assert (
            message.render(RenderMode.DISPLAY)
            == "[Error: Recursive rendering detected]"
        )
    finally:
        stack.discard(render_key)
