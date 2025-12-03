from __future__ import annotations

from types import SimpleNamespace

import pytest
from good_agent.content import FileContentPart, ImageContentPart, RenderMode
from good_agent.messages import Message, UserMessage
from good_agent.model.formatting import MessageFormatter


class _DummyContext:
    def __init__(self, output):
        self.return_value = output


class _DummyEvents:
    async def apply(self, *_, **kwargs):
        return _DummyContext(kwargs.get("output"))


def _make_factory(name: str):
    def factory(**kwargs):
        return {"__type__": name, **kwargs}

    return factory


class _FakeLanguageModel:
    def __init__(self):
        self.agent = SimpleNamespace(events=_DummyEvents())

    def _get_litellm_type(self, name: str):
        return _make_factory(name)


@pytest.mark.asyncio
async def test_format_message_content_preserves_image_detail():
    formatter = MessageFormatter(_FakeLanguageModel())
    part = ImageContentPart.from_url("https://example.com/image.png", detail="high")
    message: Message = UserMessage("see image")

    payload = await formatter.format_message_content([part], message, RenderMode.LLM)

    assert payload[0]["image_url"]["url"] == "https://example.com/image.png"
    assert payload[0]["image_url"]["detail"] == "high"


@pytest.mark.asyncio
async def test_format_message_content_normalizes_base64_images():
    formatter = MessageFormatter(_FakeLanguageModel())
    part = ImageContentPart(image_base64="rawbase64==", detail="low")
    message: Message = UserMessage("see encoded")

    payload = await formatter.format_message_content([part], message, RenderMode.LLM)

    assert payload[0]["image_url"]["url"].startswith("data:image/jpeg;base64,rawbase64")
    assert payload[0]["image_url"]["detail"] == "low"


@pytest.mark.asyncio
async def test_format_message_content_emits_file_payload():
    formatter = MessageFormatter(_FakeLanguageModel())
    part = FileContentPart.from_file_id(
        "file-789", mime_type="application/pdf", file_name="report.pdf"
    )
    message: Message = UserMessage("see attached")

    payload = await formatter.format_message_content([part], message, RenderMode.LLM)

    file_payload = payload[0]
    assert file_payload.get("file", {}).get("file_id") == "file-789"
    assert file_payload["file"].get("format") == "application/pdf"
    assert file_payload["file"].get("filename") == "report.pdf"
