from __future__ import annotations

from typing import Any, Generic, Literal, TypeAlias, TypeVar, overload

from pydantic import BaseModel

from good_agent.core.types import URL
from good_agent.messages.base import (
    IMAGE,
    Annotation,
    AnnotationLike,
    ImageDetail,
    Message,
    MessageContent,
    RenderMode,
)
from good_agent.tools import ToolCall, ToolResponse

CitationURL: TypeAlias = URL


class UserMessage(Message):
    """User message with optional images and image detail settings."""

    @overload
    def __init__(self, content: str | None = None, **data: Any): ...

    @overload
    def __init__(self, *content: MessageContent, **data: Any): ...

    def __init__(self, *args, **kwargs: Any):
        super().__init__(*args, **kwargs)

    role: Literal["user"] = "user"  # type: ignore[assignment]
    images: list[IMAGE] | None = None
    image_detail: ImageDetail | None = "auto"


class SystemMessage(Message):
    """System message for providing instructions to the LLM."""

    @overload
    def __init__(self, content: str | None = None, **data: Any): ...

    @overload
    def __init__(self, *content: MessageContent, **data: Any): ...

    def __init__(self, *args, **kwargs: Any):
        super().__init__(*args, **kwargs)

    role: Literal["system"] = "system"  # type: ignore[assignment]


T_ToolResponse = TypeVar("T_ToolResponse", bound=ToolResponse)


class ToolMessage(Message, Generic[T_ToolResponse]):
    """Tool response message containing the result of a tool execution."""

    @overload
    def __init__(
        self,
        content: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_response: T_ToolResponse | None = None,
        **data: Any,
    ): ...

    @overload
    def __init__(
        self,
        *content: MessageContent,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_response: T_ToolResponse | None = None,
        **data: Any,
    ): ...

    @overload
    def __init__(self, *content: MessageContent, **data: Any): ...

    def __init__(self, *args, **kwargs: Any):
        # Handle tool_name to name aliasing
        if "tool_name" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs["tool_name"]
        elif "name" in kwargs and "tool_name" not in kwargs:
            kwargs["tool_name"] = kwargs["name"]
        super().__init__(*args, **kwargs)

    role: Literal["tool"] = "tool"  # type: ignore[assignment]
    tool_call_id: str
    tool_name: str  # Name of the tool that was called
    tool_response: T_ToolResponse | None = None

    def __display__(self) -> str:
        """Protocol method for display rendering.

        Wraps XML/HTML content in code blocks to prevent markdown interpretation issues.
        """
        content = self.render(RenderMode.DISPLAY)

        if not content:
            return ""

        # Check if content looks like XML/HTML
        content_stripped = content.strip()
        if content_stripped and (
            (content_stripped.startswith("<") and content_stripped.endswith(">"))
            or "</" in content_stripped[:100]  # Check for closing tags in first 100 chars
        ):
            # Wrap in XML code block for proper display
            return f"```xml\n{content_stripped}\n```"

        # For non-XML content, return as-is
        return content


class AssistantMessage(Message):
    """Assistant message with optional tool calls, reasoning, and citations."""

    @overload
    def __init__(self, content: str | None = None, **data): ...

    @overload
    def __init__(
        self,
        *content: MessageContent,
        tool_calls: list[ToolCall] | None = None,
        reasoning: str | None = None,
        refusal: str | None = None,
        citations: list[CitationURL] | None = None,
        annotations: list[AnnotationLike] | None = None,
        **data: Any,
    ): ...

    @overload
    def __init__(self, *content: MessageContent, **data: Any): ...

    def __init__(self, *args, **kwargs: Any):
        super().__init__(*args, **kwargs)

    role: Literal["assistant"] = "assistant"  # type: ignore[assignment]
    tool_calls: list[ToolCall] | None = None
    reasoning: str | None = None
    refusal: str | None = None
    citations: list[CitationURL] | None = None
    annotations: list[AnnotationLike] | None = None

    @property
    def reasoning_content(self) -> str | None:
        """Compatibility alias for providers that return reasoning_content."""
        return self.reasoning

    def __display__(self) -> str:
        """Protocol method for display rendering.

        Returns rendered content or empty string for tool-only messages.
        """
        content = self.render(RenderMode.DISPLAY)
        # If we have no content but do have tool calls, return empty string
        # This signals to print_message that we have a tool-only message
        if not content and self.tool_calls:
            return ""
        return content


T_Output = TypeVar("T_Output", bound=BaseModel)


class AssistantMessageStructuredOutput(AssistantMessage, Generic[T_Output]):
    """Assistant message with structured output conforming to a Pydantic model."""

    output: T_Output

    def __display__(self) -> str:
        """Display structured output as YAML."""
        from good_common.utilities import yaml_dumps  # type: ignore[import-untyped]

        return yaml_dumps(self.output.model_dump(mode="json"))


__all__ = [
    "UserMessage",
    "SystemMessage",
    "ToolMessage",
    "AssistantMessage",
    "AssistantMessageStructuredOutput",
    "T_ToolResponse",
    "T_Output",
    "CitationURL",
    "Annotation",
]

# Rebuild models to resolve forward references (required for Python 3.14+)
AssistantMessage.model_rebuild()
AssistantMessageStructuredOutput.model_rebuild()
