import base64
import re
from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Discriminator,
    Field,
    model_validator,
)


def is_template(text: str) -> bool:
    """Check if text contains Jinja2 template syntax.

    Args:
        text: String to check for template patterns

    Returns:
        True if text appears to be a Jinja2 template
    """
    # Check for Jinja2 variable, block, comment syntax, or line statements
    patterns = [
        r"{{.*?}}",  # Variables: {{ variable }}
        r"{%.*?%}",  # Blocks: {% if condition %}
        r"{#.*?#}",  # Comments: {# comment #}
        r"^\s*#\s*(for|if|elif|else|endif|endfor|block|endblock|extends|include)",  # Line statements with optional leading whitespace
        r"^\s*!#\s*(for|if|elif|else|endif|endfor|block|endblock|extends|include)",  # Jinja2 line statements with !# prefix
    ]
    return bool(re.search("|".join(patterns), text, re.MULTILINE))


class RenderMode(Enum):
    """Rendering context for content parts."""

    LLM = "llm"
    DISPLAY = "display"
    STORAGE = "storage"
    EXPORT = "export"
    RAW = "raw"  # Raw content representation without formatting


def _process_text(text: str):
    import textwrap

    return textwrap.dedent(text).strip()


PROCESSED_TEXT = Annotated[str, BeforeValidator(_process_text)]


class BaseContentPart(BaseModel):
    """Base class for all serializable content parts."""

    model_config = ConfigDict(arbitrary_types_allowed=False, extra="forbid")

    type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextContentPart(BaseContentPart):
    """Plain text content."""

    type: Literal["text"] = "text"
    text: PROCESSED_TEXT

    def render(self, mode: RenderMode, context: dict[str, Any] | None = None) -> str:
        """Render text content.

        Args:
            mode: The rendering mode
            context: Optional rendering context

        Returns:
            Text content (same for all modes)
        """
        if mode == RenderMode.RAW:
            # For RAW mode, return the raw representation
            return repr(self.text)
        return self.text

    def to_llm_format(self) -> dict[str, Any]:
        """Convert to LLM API format."""
        return {"type": "text", "text": self.text}


class TemplateContentPart(BaseContentPart):
    """Jinja2 template content with context management."""

    type: Literal["template"] = "template"
    template: PROCESSED_TEXT
    context_requirements: list[str] = Field(default_factory=list)
    context_snapshot: dict[str, Any] | None = None
    rendered_cache: dict[str, str] = Field(default_factory=dict)

    def render(
        self,
        mode: RenderMode,
        context: dict[str, Any] | None = None,
        template_manager: Any | None = None,
    ) -> str:
        """Render template with provided context.

        Args:
            mode: The rendering mode
            context: Rendering context dictionary
            template_manager: Optional template manager for rendering

        Returns:
            Rendered string
        """
        # For RAW mode, return the template source itself
        if mode == RenderMode.RAW:
            snapshot_preview = None
            if self.context_snapshot:
                # Show a preview of context snapshot
                snapshot_preview = repr(dict(list(self.context_snapshot.items())[:3]))
                if len(self.context_snapshot) > 3:
                    snapshot_preview = snapshot_preview[:-1] + ", ...}"
            return f"TemplateContentPart(template={repr(self.template[:100] + '...' if len(self.template) > 100 else self.template)}, context_snapshot={snapshot_preview})"

        # Check cache first
        mode_key = mode.value
        if mode_key in self.rendered_cache:
            return self.rendered_cache[mode_key]

        # Build render context
        render_context = context or {}
        if self.context_snapshot:
            # Snapshot overrides provided context
            render_context = {**render_context, **self.context_snapshot}

        # Add render mode to context
        render_context["render_mode"] = mode.value

        # Render template
        try:
            if template_manager:
                rendered = template_manager.render_template(self.template, render_context)
            else:
                # Simple Jinja2 fallback with sandbox by default
                from good_agent.core import templating

                # Create sandboxed environment
                env = templating.create_environment(use_sandbox=True)
                template = env.from_string(self.template)
                rendered = template.render(**render_context)
        except Exception:
            # Re-raise template errors to make them fatal
            raise

        # Cache result
        self.rendered_cache[mode_key] = rendered
        return str(rendered)

    def to_llm_format(self) -> dict[str, Any]:
        """Convert to LLM API format (rendered as text)."""
        # Templates are rendered before sending to LLM
        # This requires access to the message/agent context
        # which will be handled at a higher level
        return {"type": "text", "text": self.template}  # Fallback


class ImageContentPart(BaseContentPart):
    """Image content for multimodal models."""

    type: Literal["image"] = "image"
    image_url: str | None = None
    image_base64: str | None = None
    detail: Literal["high", "low", "auto"] = "auto"
    mime_type: str | None = None

    @staticmethod
    def _extract_mime_type(data_url: str) -> str | None:
        if not data_url.startswith("data:"):
            return None
        header = data_url.split(";", 1)[0]
        if header.startswith("data:"):
            return header[5:] or None
        return None

    @model_validator(mode="after")
    def _validate_and_normalize(self) -> ImageContentPart:
        if self.image_url and self.image_base64:
            raise ValueError("image_url and image_base64 are mutually exclusive")

        if self.image_base64:
            normalized = self.image_base64.strip()
            if not normalized.startswith("data:"):
                mime = self.mime_type or "image/jpeg"
                normalized = f"data:{mime};base64,{normalized}"
            self.image_base64 = normalized
            if not self.mime_type:
                self.mime_type = type(self)._extract_mime_type(normalized)

        return self

    @classmethod
    def from_url(
        cls, url: str, *, detail: Literal["high", "low", "auto"] = "auto"
    ) -> ImageContentPart:
        return cls(image_url=url, detail=detail)

    @classmethod
    def from_base64(
        cls,
        data: str,
        *,
        detail: Literal["high", "low", "auto"] = "auto",
        mime_type: str | None = None,
    ) -> ImageContentPart:
        return cls(image_base64=data, detail=detail, mime_type=mime_type)

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        *,
        detail: Literal["high", "low", "auto"] = "auto",
        mime_type: str | None = None,
    ) -> ImageContentPart:
        detected_mime = mime_type
        if detected_mime is None:
            try:
                import magic

                detected_mime = magic.Magic(mime=True).from_buffer(data)
            except Exception:
                detected_mime = "image/jpeg"

        prefix = f"data:{detected_mime};base64,"
        encoded = base64.b64encode(data).decode("utf-8")
        return cls(
            image_base64=f"{prefix}{encoded}",
            detail=detail,
            mime_type=detected_mime,
        )

    def render(self, mode: RenderMode, context: dict[str, Any] | None = None) -> str:
        """Render image content as string description.

        Args:
            mode: The rendering mode
            context: Optional rendering context

        Returns:
            String representation of the image
        """
        if mode == RenderMode.RAW:
            # For RAW mode, return the raw data representation
            if self.image_url:
                return f"ImageContentPart(url={repr(self.image_url)}, detail={repr(self.detail)})"
            elif self.image_base64:
                preview = (
                    self.image_base64[:50] + "..."
                    if len(self.image_base64) > 50
                    else self.image_base64
                )
                return f"ImageContentPart(base64={repr(preview)}, detail={repr(self.detail)})"
            return "ImageContentPart(no source)"

        # Default rendering for other modes
        if self.image_url:
            return f"[Image: {self.image_url}]"
        elif self.image_base64:
            return f"[Image: base64 encoded, detail={self.detail}]"
        return "[Image: no source]"

    def to_llm_format(self) -> dict[str, Any]:
        """Convert to LLM API format."""
        if self.image_url:
            payload: dict[str, Any] = {
                "type": "image_url",
                "image_url": {"url": self.image_url, "detail": self.detail},
            }
            if self.mime_type:
                payload["image_url"]["mime_type"] = self.mime_type
            return payload
        elif self.image_base64:
            url = self.image_base64
            if not url.startswith("data:"):
                mime = self.mime_type or "image/jpeg"
                url = f"data:{mime};base64,{url}"
            payload = {
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": self.detail,
                },
            }
            if self.mime_type:
                payload["image_url"]["mime_type"] = self.mime_type
            return payload
        raise ValueError("Image content must have either url or base64")


class FileContentPart(BaseContentPart):
    """File attachment content."""

    type: Literal["file"] = "file"
    file_path: str | None = None
    file_content: str | None = None
    mime_type: str | None = None
    file_name: str | None = None

    @model_validator(mode="after")
    def _validate_source(self) -> FileContentPart:
        if self.file_path and self.file_content:
            raise ValueError("file_path and file_content are mutually exclusive")
        return self

    @classmethod
    def from_file_id(
        cls, file_id: str, *, mime_type: str | None = None, file_name: str | None = None
    ) -> FileContentPart:
        return cls(file_path=file_id, mime_type=mime_type, file_name=file_name)

    @classmethod
    def from_content(
        cls, content: str, *, mime_type: str | None = None, file_name: str | None = None
    ) -> FileContentPart:
        return cls(file_content=content, mime_type=mime_type, file_name=file_name)

    def render(self, mode: RenderMode, context: dict[str, Any] | None = None) -> str:
        """Render file content as string description.

        Args:
            mode: The rendering mode
            context: Optional rendering context

        Returns:
            String representation of the file
        """
        if mode == RenderMode.RAW:
            # For RAW mode, return the raw data representation
            if self.file_path:
                return f"FileContentPart(path={repr(self.file_path)}, mime_type={repr(self.mime_type)})"
            elif self.file_content:
                preview = (
                    self.file_content[:50] + "..."
                    if len(self.file_content) > 50
                    else self.file_content
                )
                return f"FileContentPart(content={repr(preview)}, mime_type={repr(self.mime_type)})"
            return "FileContentPart(no content)"

        # Default rendering for other modes
        if self.file_path:
            return f"[File: {self.file_path}]"
        elif self.file_content:
            preview = (
                self.file_content[:100] + "..."
                if len(self.file_content) > 100
                else self.file_content
            )
            return f"[File content: {preview}]"
        return "[File: no content]"

    def to_llm_format(self) -> dict[str, Any]:
        """Convert to LLM API format."""
        # Files are typically converted to text for LLMs
        if self.file_content:
            return {"type": "text", "text": self.file_content}
        elif self.file_path:
            file_payload: dict[str, Any] = {
                "type": "file",
                "file": {"file_id": self.file_path},
            }
            if self.mime_type:
                file_payload["file"]["format"] = self.mime_type
            if self.file_name:
                file_payload["file"]["filename"] = self.file_name
            return file_payload
        return {"type": "text", "text": "[File: no content]"}


# Discriminated union for efficient parsing
ContentPartType = Annotated[
    TextContentPart | TemplateContentPart | ImageContentPart | FileContentPart,
    Discriminator("type"),
]


def deserialize_content_part(data: dict[str, Any]) -> ContentPartType:
    """Deserialize a content part from dictionary.

    Args:
        data: Dictionary representation of content part

    Returns:
        Appropriate content part instance
    """
    if not isinstance(data, dict) or "type" not in data:
        raise ValueError(f"Invalid content part data: {data}")

    part_type = data["type"]
    if part_type == "text":
        return TextContentPart.model_validate(data)
    elif part_type == "template":
        return TemplateContentPart.model_validate(data)
    elif part_type == "image":
        return ImageContentPart.model_validate(data)
    elif part_type == "file":
        return FileContentPart.model_validate(data)
    else:
        raise ValueError(f"Unknown content part type: {part_type}")
