import json

import pytest

from good_agent.content import (
    FileContentPart,
    ImageContentPart,
    RenderMode,
    TemplateContentPart,
    TextContentPart,
    deserialize_content_part,
)


class TestContentPartSerialization:
    """Test serialization and deserialization of content parts."""

    def test_text_part_serialization(self):
        """Test TextContentPart serialization."""
        part = TextContentPart(text="Hello world")
        data = part.model_dump()
        assert data == {"type": "text", "text": "Hello world", "metadata": {}}

        # Round trip
        restored = TextContentPart.model_validate(data)
        assert restored == part
        assert restored.text == "Hello world"

    def test_template_part_serialization(self):
        """Test TemplateContentPart serialization."""
        part = TemplateContentPart(
            template="Hello {{ name }}",
            context_requirements=["name"],
            context_snapshot={"name": "Alice"},
        )
        data = part.model_dump()

        # Verify structure
        assert data["type"] == "template"
        assert data["template"] == "Hello {{ name }}"
        assert data["context_requirements"] == ["name"]
        assert data["context_snapshot"] == {"name": "Alice"}

        # Round trip
        restored = TemplateContentPart.model_validate(data)
        assert restored.template == part.template
        assert restored.context_requirements == part.context_requirements

    def test_image_part_serialization(self):
        """Test ImageContentPart serialization."""
        part = ImageContentPart(image_url="https://example.com/image.jpg", detail="high")
        data = part.model_dump()

        assert data["type"] == "image"
        assert data["image_url"] == "https://example.com/image.jpg"
        assert data["detail"] == "high"

        # Round trip
        restored = ImageContentPart.model_validate(data)
        assert restored == part

    def test_file_part_serialization(self):
        """Test FileContentPart serialization."""
        part = FileContentPart(file_path="/path/to/file.txt", mime_type="text/plain")
        data = part.model_dump()

        assert data["type"] == "file"
        assert data["file_path"] == "/path/to/file.txt"
        assert data["mime_type"] == "text/plain"

        # Round trip
        restored = FileContentPart.model_validate(data)
        assert restored == part

    def test_discriminated_union_parsing(self):
        """Test parsing with discriminated union."""
        # Parse text part
        text_data = {"type": "text", "text": "Hello"}
        part = deserialize_content_part(text_data)
        assert isinstance(part, TextContentPart)
        assert part.text == "Hello"

        # Parse template part
        template_data = {"type": "template", "template": "{{ x }}"}
        part = deserialize_content_part(template_data)
        assert isinstance(part, TemplateContentPart)
        assert part.template == "{{ x }}"

        # Parse image part
        image_data = {"type": "image", "image_url": "http://example.com/img.jpg"}
        part = deserialize_content_part(image_data)
        assert isinstance(part, ImageContentPart)
        assert part.image_url == "http://example.com/img.jpg"

    def test_json_serialization(self):
        """Test that content parts can be JSON serialized."""
        parts = [
            TextContentPart(text="Hello"),
            TemplateContentPart(template="{{ name }}"),
            ImageContentPart(image_url="http://example.com/img.jpg"),
        ]

        # Should be JSON serializable
        for part in parts:
            json_str = json.dumps(part.model_dump())
            restored_data = json.loads(json_str)
            restored_part = deserialize_content_part(restored_data)
            assert restored_part.model_dump() == part.model_dump()


class TestTemplateRendering:
    """Test template rendering functionality."""

    def test_template_render_with_context(self):
        """Test template rendering with context."""
        part = TemplateContentPart(
            template="Hello {{ name }}, you have {{ count }} messages",
            context_requirements=["name", "count"],
        )

        rendered = part.render(RenderMode.DISPLAY, context={"name": "Bob", "count": 5})
        assert rendered == "Hello Bob, you have 5 messages"

    def test_template_cache(self):
        """Test template rendering cache."""
        part = TemplateContentPart(template="Static {{ value }}")

        # First render
        rendered1 = part.render(RenderMode.DISPLAY, context={"value": "A"})
        assert rendered1 == "Static A"
        assert RenderMode.DISPLAY.value in part.rendered_cache

        # Second render uses cache (same value returned)
        rendered2 = part.render(RenderMode.DISPLAY, context={"value": "B"})
        assert rendered2 == "Static A"  # Cached value

    def test_template_render_modes(self):
        """Test different render modes."""
        part = TemplateContentPart(template="Mode: {{ render_mode }}")

        # Render for LLM
        llm_render = part.render(RenderMode.LLM, context={})
        assert "llm" in llm_render

        # Render for display
        display_render = part.render(RenderMode.DISPLAY, context={})
        assert "display" in display_render

    def test_template_with_snapshot(self):
        """Test template with context snapshot."""
        part = TemplateContentPart(
            template="Hello {{ name }}", context_snapshot={"name": "Snapshot"}
        )

        # Snapshot has priority over passed context
        rendered = part.render(RenderMode.DISPLAY, context={"name": "Context"})
        assert rendered == "Hello Snapshot"


class TestContentPartFormats:
    """Test LLM API format generation."""

    def test_text_to_llm_format(self):
        """Test TextContentPart LLM format."""
        part = TextContentPart(text="Hello world")
        llm_format = part.to_llm_format()

        assert llm_format == {"type": "text", "text": "Hello world"}

    def test_image_to_llm_format(self):
        """Test ImageContentPart LLM format."""
        # With URL
        part = ImageContentPart(image_url="https://example.com/image.jpg", detail="high")
        llm_format = part.to_llm_format()

        assert llm_format == {
            "type": "image_url",
            "image_url": {"url": "https://example.com/image.jpg", "detail": "high"},
        }

        # With base64
        part = ImageContentPart(image_base64="base64data", detail="low")
        llm_format = part.to_llm_format()

        assert llm_format == {
            "type": "image_url",
            "image_url": {
                "url": "data:image/jpeg;base64,base64data",
                "detail": "low",
                "mime_type": "image/jpeg",
            },
        }
        assert part.mime_type == "image/jpeg"

    def test_file_to_llm_format(self):
        """Test FileContentPart LLM format."""
        part = FileContentPart(file_content="File contents here")
        llm_format = part.to_llm_format()

        assert llm_format == {"type": "text", "text": "File contents here"}

        reference = FileContentPart(
            file_path="file-123", mime_type="application/pdf", file_name="spec.pdf"
        )
        llm_payload = reference.to_llm_format()

        assert llm_payload == {
            "type": "file",
            "file": {
                "file_id": "file-123",
                "format": "application/pdf",
                "filename": "spec.pdf",
            },
        }

    def test_image_content_helpers(self):
        part_from_url = ImageContentPart.from_url("https://example.com/test.png", detail="high")
        assert part_from_url.image_url == "https://example.com/test.png"
        assert part_from_url.detail == "high"

        data_url = "data:image/png;base64,ZXhhbXBsZQ=="
        part_from_base64 = ImageContentPart.from_base64(data_url, detail="low")
        assert part_from_base64.image_base64 == data_url
        assert part_from_base64.mime_type == "image/png"

        part_from_bytes = ImageContentPart.from_bytes(b"binarydata", mime_type="image/gif")
        assert part_from_bytes.image_base64.startswith("data:image/gif;base64,")
        assert part_from_bytes.mime_type == "image/gif"

    def test_file_content_helpers(self):
        part_from_id = FileContentPart.from_file_id(
            "file-456", mime_type="application/json", file_name="data.json"
        )
        assert part_from_id.file_path == "file-456"
        assert part_from_id.mime_type == "application/json"
        assert part_from_id.file_name == "data.json"

        part_from_content = FileContentPart.from_content(
            "inline text", mime_type="text/plain", file_name="note.txt"
        )
        assert part_from_content.file_content == "inline text"
        assert part_from_content.mime_type == "text/plain"
        assert part_from_content.file_name == "note.txt"

    def test_mutually_exclusive_fields(self):
        with pytest.raises(ValueError):
            ImageContentPart(image_url="https://example.com/img.png", image_base64="abc")

        with pytest.raises(ValueError):
            FileContentPart(file_path="file-123", file_content="inline")


class TestRenderModes:
    """Test different render modes for content parts."""

    def test_text_render_modes(self):
        """Test TextContentPart render modes."""
        part = TextContentPart(text="Hello world")

        # All modes return same text
        assert part.render(RenderMode.LLM) == "Hello world"
        assert part.render(RenderMode.DISPLAY) == "Hello world"
        assert part.render(RenderMode.STORAGE) == "Hello world"
        assert part.render(RenderMode.EXPORT) == "Hello world"

    def test_image_render_modes(self):
        """Test ImageContentPart render modes."""
        part = ImageContentPart(image_url="https://example.com/img.jpg")

        # All modes return description
        rendered = part.render(RenderMode.DISPLAY)
        assert "Image" in rendered
        assert "https://example.com/img.jpg" in rendered
