from __future__ import annotations

import datetime
import logging
import threading
import weakref
from abc import ABC
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Literal,
    Self,
    TypeAlias,
    overload,
)

from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from ulid import ULID

# Import content parts
from good_agent.content import (
    ContentPartType,
    FileContentPart,
    ImageContentPart,
    RenderMode,
    TemplateContentPart,
    TextContentPart,
    deserialize_content_part,
    is_template,
)
from good_agent.core.models import GoodBase, PrivateAttrBase
from good_agent.core.types import URL
from good_agent.core.ulid_monotonic import create_monotonic_ulid
from good_agent.utilities.typing import (
    SupportsDisplay,
    SupportsLLM,
    SupportsRender,
    SupportsString,
)

if TYPE_CHECKING:
    from good_agent.agent import Agent
    from good_agent.messages.roles import (
        AssistantMessage,
        SystemMessage,
        ToolMessage,
        UserMessage,
    )

logger = logging.getLogger(__name__)

# Thread-local storage for tracking render calls to prevent recursion
_render_guard = threading.local()


def _get_render_stack() -> set[str]:
    """Get the current thread's render call stack."""
    if not hasattr(_render_guard, "stack"):
        _render_guard.stack = set()
    return _render_guard.stack


MessageRole = Literal["system", "user", "assistant", "tool"]
ImageDetail = Literal["high", "low", "auto"]

IMAGE: TypeAlias = "URL | bytes"
MessageContent: TypeAlias = (
    "Message | SupportsLLM | SupportsDisplay | SupportsString | SupportsRender | str"
)


class Annotation(BaseModel):
    """Message annotation with text span and metadata."""

    text: str
    start: int
    end: int
    metadata: dict[str, Any] = Field(default_factory=dict)


AnnotationLike: TypeAlias = "Annotation | dict[str, Any]"


class Message(PrivateAttrBase, GoodBase, ABC):
    """Base message class with content parts and multi-mode rendering.

    Messages support mixed content (text, templates, images, files) and render
    differently for LLM consumption vs display. Template parts use Jinja2 with
    context from the agent.

    Args:
        *content: Content parts or strings to compose the message
        **kwargs: Additional message fields

    Example:
        >>> msg = UserMessage("Hello, world!")
        >>> msg = SystemMessage("You are a {role} assistant", context={"role": "helpful"})
    """

    model_config = ConfigDict(
        frozen=True,
        extra="allow",
    )

    # Public field for new content parts
    content_parts: list[ContentPartType] = Field(default_factory=list)

    # Citation URLs list (not sent to LLM for all message types)
    citations: list[URL] | None = None

    def __repr__(self):
        """Ensure content is excluded to prevent recursion."""
        _type = self.__class__.__name__
        return f'<{_type} id="{self.id}" />'

    @classmethod
    def _create_content_part(
        cls,
        content: Any,
        template_detection: bool = True,
    ) -> ContentPartType:
        """Factory method to create appropriate ContentPart type.

        Args:
            content: The content to convert to a ContentPart
            template_detection: Whether to detect templates in strings

        Returns:
            Appropriate ContentPart instance
        """
        # Check if it's already a new-style content part
        if isinstance(
            content,
            (TextContentPart, TemplateContentPart, ImageContentPart, FileContentPart),
        ):
            return content

        # Check if it's already a Message (for composability)
        if isinstance(content, Message):
            # Extract and combine content parts from the message
            parts = []
            for part in content.content_parts:
                parts.append(part)
            # If multiple parts, return as text representation
            if len(parts) == 1:
                return parts[0]
            else:
                # Combine into single text part
                combined_text = "\n".join(part.render(RenderMode.DISPLAY) for part in parts)
                return TextContentPart(text=combined_text)

        # Check for protocol support using isinstance
        if isinstance(content, (SupportsLLM, SupportsDisplay)):
            if isinstance(content, SupportsLLM):
                text = content.__llm__()
            elif isinstance(content, SupportsDisplay):
                text = content.__display__()
            else:
                text = str(content)
            return TextContentPart(text=text)

        # Convert to string for template detection
        content_str = str(content) if content is not None else ""

        # Detect templates if enabled
        if template_detection and is_template(content_str):
            return TemplateContentPart(
                template=content_str,
                context_requirements=[],  # Will be populated when attached to agent
            )
        else:
            # Plain string content
            return TextContentPart(text=content_str)

    @classmethod
    def _parse_content(
        cls,
        *content_parts: MessageContent,
        template_detection: bool = True,
    ) -> list[ContentPartType]:
        """Parse various content inputs into serializable content parts."""
        parts = []
        for part in content_parts:
            if isinstance(
                part,
                (
                    TextContentPart,
                    TemplateContentPart,
                    ImageContentPart,
                    FileContentPart,
                ),
            ):
                # Already a new content part
                parts.append(part)
            elif isinstance(part, dict) and "type" in part:
                # Parse from serialized format
                parts.append(deserialize_content_part(part))
            elif isinstance(part, Message):
                # Extract content parts from message
                parts.extend(part.content_parts)
            else:
                # Create new content part
                content_part = cls._create_content_part(part, template_detection=template_detection)
                parts.append(content_part)
        return parts

    __match_args__: ClassVar[tuple[str, ...]] = (  # type: ignore[misc]
        "role",
        "content",
        "tool_response",
        "output",
        "i",
        "ok",
        "index",
        "attempt",
        "retry",
        "last_attempt",
        "agent",
    )

    # Rendering cache
    _rendered_cache: dict[RenderMode, str] = PrivateAttr(default_factory=dict)
    _context: dict[str, Any] = PrivateAttr(default_factory=dict)

    # Token counting cache keyed by "{model}:{include_tools}"
    _token_count_cache: dict[str, int] = PrivateAttr(default_factory=dict)

    # Legacy support
    _raw_content: str | None = PrivateAttr(default=None)
    _rendered_content: str | None = PrivateAttr(default=None)
    _legacy_content_fallback: str | None = PrivateAttr(default=None)

    # Execution context attributes
    _ok: bool = PrivateAttr(default=True)
    _attempt: int = PrivateAttr(default=1)
    _retry: bool = PrivateAttr(default=False)
    _last_attempt: bool = PrivateAttr(default=False)
    _i: int | None = PrivateAttr(default=None)
    _agent_ref: weakref.ref[Agent] | None = PrivateAttr(default=None)

    id: ULID = Field(default_factory=create_monotonic_ulid)

    def __init__(
        self,
        *content: MessageContent,
        **kwargs,
    ):
        # Process content normally
        legacy_content_arg = kwargs.pop("legacy_content", None)
        _content: list[Any] = []

        if "_content" in kwargs:
            # Legacy private attribute no longer supported
            raise ValueError(
                "Legacy _content attribute is no longer supported. Use content_parts instead."
            )
        else:
            content = kwargs.pop("content", None) or content

            if content:
                if isinstance(content, str):
                    _content = [content]
                elif isinstance(content, (list, tuple)):
                    _content = list(content)  # type: ignore[misc]
                else:
                    raise TypeError(
                        f"Invalid content type: {type(content)}. Expected str, list, or tuple."
                    )

            # Handle template parameter
            template = kwargs.pop("template", None)
            if template:
                # Always set raw_content for backward compatibility when template is provided
                if isinstance(template, str):
                    self._raw_content = template
                    # If no content provided, use template as content
                    if not content:
                        _content.append(template)
                elif isinstance(template, (list, tuple)):
                    self._raw_content = "\n".join(str(t) for t in template)
                    # If no content provided, use template as content
                    if not content:
                        _content.extend(template)

            # Parse content into new format
            if "content_parts" not in kwargs:
                kwargs["content_parts"] = self._parse_content(
                    *_content, template_detection=kwargs.pop("template_detection", True)
                )

        fallback_seed: str | None = None
        if not kwargs.get("content_parts") and _content:
            fallback_seed = "\n".join(str(part) for part in _content if part is not None)

        super().__init__(**kwargs)

        # Finalize content parts (extract template variables if agent is set)
        self._finalize_content_parts()

        fallback_value = legacy_content_arg if legacy_content_arg is not None else fallback_seed
        if fallback_value:
            self._legacy_content_fallback = str(fallback_value)

    def _finalize_content_parts(self) -> None:
        """Finalize content parts after message creation."""
        if self.agent is not None and self.agent.template:
            for part in self.content_parts:
                if isinstance(part, TemplateContentPart) and not part.context_requirements:
                    # Extract template variables using TemplateManager
                    part.context_requirements = self.agent.template.extract_template_variables(
                        part.template
                    )

    def render(self, mode: RenderMode = RenderMode.DISPLAY) -> str:
        """Render message content for specific context.

        This is a pure rendering method that converts content parts to strings
        without any event handling. Event-based rendering for LLM consumption
        happens in LanguageModel.format_message_list_for_llm.

        Args:
            mode: The rendering context (LLM, DISPLAY, etc.)

        Returns:
            Rendered message content
        """
        logger.debug(f"Rendering message {self.id} with mode {mode}")
        # Create unique key for this message + mode combination
        render_key = f"{id(self)}:{mode.value}"
        logger.debug(f"Render key: {render_key}")
        render_stack = _get_render_stack()

        # Check for recursion
        if render_key in render_stack:
            # Recursion detected - return cached content or fallback
            logger.warning(
                f"Recursion detected in Message.render() for message {self.id} with mode {mode}"
            )

            # Try to return cached content if available
            if mode in self._rendered_cache:
                return self._rendered_cache[mode]
            else:
                return "[Error: Recursive rendering detected]"

        # Mark this render call as in progress
        render_stack.add(render_key)

        try:
            # Check cache first (but not for templates which may change)
            if mode in self._rendered_cache and not self._has_templates():
                logger.debug(f"Using cached rendered content for message {self.id}")
                return self._rendered_cache[mode]

            # Ensure we have content parts to render
            if not self.content_parts:
                logger.debug(f"No content parts to render for message {self.id}")

                fallback_content = self._legacy_content_fallback or self._raw_content
                if fallback_content is None:
                    legacy_attr = getattr(self, "legacy_content", None)
                    if isinstance(legacy_attr, str):
                        fallback_content = legacy_attr

                return fallback_content or ""

            # Fire BEFORE event to allow components to modify content_parts
            content_parts = self.content_parts
            if self.agent is not None:
                from good_agent.events import AgentEvents

                try:
                    # Fire BEFORE event with content_parts (not yet rendered)
                    # Components can modify the parts before rendering
                    ctx = self.agent.events.apply_sync(
                        AgentEvents.MESSAGE_RENDER_BEFORE,
                        message=self,
                        mode=mode,
                        output=list(content_parts),  # Pass parts, not rendered string
                    )
                except Exception as exc:  # noqa: BLE001 - propagate gracefully for render
                    logger.warning(
                        "Message render handler failed for %s (%s mode): %s",
                        self.id,
                        mode,
                        exc,
                        exc_info=True,
                    )
                else:
                    # Use modified content_parts if handlers transformed them
                    content_parts = ctx.parameters.get("output", content_parts)

            # Render content parts using the centralized _render_part method
            rendered_parts = []
            for part in content_parts:
                try:
                    rendered = self._render_part(part, mode)
                except Exception as e:
                    # Re-raise template errors to make them fatal
                    if isinstance(part, TemplateContentPart):
                        # Template errors should be fatal
                        raise
                    else:
                        # For non-template parts, fall back to safe representation
                        rendered = str(part)
                        logger.debug(f"Error rendering non-template part: {e}")

                rendered_parts.append(rendered)

            content = "\n".join(rendered_parts)

            # Fire AFTER event for notification (read-only)
            if self.agent is not None:
                self.agent.do(
                    AgentEvents.MESSAGE_RENDER_AFTER,
                    message=self,
                    mode=mode,
                    rendered_content=content,
                )

            # Cache if appropriate
            if self._should_cache(mode):
                self._rendered_cache[mode] = content

            return content

        finally:
            # Always clean up the render call marker
            render_stack.discard(render_key)

    def _has_templates(self) -> bool:
        """Check if message contains template parts."""
        return any(isinstance(part, TemplateContentPart) for part in self.content_parts)

    def _should_cache(self, mode: RenderMode) -> bool:
        """Determine if rendered content should be cached."""
        # Don't cache if we have templates
        if self._has_templates():
            return False

        # Don't cache LLM context if agent exists (might have transformations)
        if mode == RenderMode.LLM:
            agent = self._agent_ref() if self._agent_ref else None
            if agent is not None:
                # Conservative: don't cache if agent exists since it might have handlers
                return False

        return True

    def __llm__(self) -> str:
        """Protocol method for LLM rendering."""
        return self.render(RenderMode.LLM)

    def __display__(self) -> str:
        """Protocol method for display rendering."""
        return self.render(RenderMode.DISPLAY)

    def __str__(self) -> str:
        """String representation for display."""
        return self.render(RenderMode.DISPLAY)

    def __len__(self) -> int:
        """Return token count for this message.

        Returns:
            Number of tokens in this message including content and tool calls
        """
        from good_agent.utilities.tokens import get_message_token_count

        # Get model from agent if available
        model = "gpt-4o"
        if self.agent is not None:
            model = self.agent.config.model

        return get_message_token_count(message=self, model=model, include_tools=True)  # type: ignore[arg-type]

    @property
    def content(self) -> str:
        """Backward compatible property - renders for display."""
        return self.render(RenderMode.DISPLAY)

    @overload
    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: Literal["assistant"]
    ) -> AssistantMessage: ...

    @overload
    @classmethod
    def from_llm_response(cls, response: dict[str, Any], role: Literal["user"]) -> UserMessage: ...

    @overload
    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: Literal["system"]
    ) -> SystemMessage: ...

    @overload
    @classmethod
    def from_llm_response(cls, response: dict[str, Any], role: Literal["tool"]) -> ToolMessage: ...

    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: MessageRole = "assistant"
    ) -> Message:
        """Create message from LLM API response.

        Args:
            response: Raw response from LLM API
            role: Message role (usually 'assistant')

        Returns:
            Appropriate Message instance with parsed content
        """
        # Normalize response shape
        msg_dict: dict[str, Any] = response
        msg_obj: Any = None  # Keep track of the actual message object
        usage_data: dict[str, Any] | None = None

        if isinstance(response, dict) and "choices" in response:
            # Treat as top-level API response
            choices = response.get("choices") or []
            first_choice = choices[0] if isinstance(choices, list) and choices else {}
            if isinstance(first_choice, dict):
                msg_dict = first_choice.get("message") or {}
            else:
                # Fallback for object-like choices
                try:
                    msg_obj = getattr(first_choice, "message", None)
                    if msg_obj:
                        # If message is an object, convert relevant fields to dict
                        msg_dict = {
                            "content": getattr(msg_obj, "content", ""),
                            "tool_calls": getattr(msg_obj, "tool_calls", None),
                            "reasoning": getattr(msg_obj, "reasoning", None),
                            "refusal": getattr(msg_obj, "refusal", None),
                            "citations": getattr(msg_obj, "citations", None),
                            "annotations": getattr(msg_obj, "annotations", None),
                            "usage": getattr(msg_obj, "usage", None),
                        }
                    else:
                        msg_dict = {}
                except Exception:
                    msg_dict = {}
            # Extract usage from the top-level response if present
            usage_data = response.get("usage")

        # Extract content from the normalized message dict
        content = msg_dict.get("content", "")

        # LLM responses are typically strings, not lists
        content_parts: list[ContentPartType]
        if isinstance(content, str):
            # Simple string response - create single text part
            content_parts = [TextContentPart(text=content)]
        elif isinstance(content, list):
            # Some LLMs might return structured content (rare)
            content_parts = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        content_parts.append(TextContentPart(text=item.get("text", "")))
                    elif item.get("type") == "image_url":
                        # Handle multimodal responses
                        image_data = item.get("image_url", {})
                        content_parts.append(
                            ImageContentPart(
                                image_url=image_data.get("url"),
                                detail=image_data.get("detail", "auto"),
                            )
                        )
                else:
                    # Fallback to text
                    content_parts.append(TextContentPart(text=str(item)))
        else:
            # Fallback for unexpected formats
            content_parts = [TextContentPart(text=str(content))]

        # Import here to avoid circular dependency
        from good_agent.messages.roles import (
            AssistantMessage,
            SystemMessage,
            ToolMessage,
            UserMessage,
        )

        # Create appropriate message type
        if role == "assistant":

            def _norm_reasoning(val: Any) -> str | None:
                if val is None:
                    return None
                if isinstance(val, str):
                    return val
                try:
                    content = getattr(val, "content", None)
                except Exception:
                    content = None
                if isinstance(content, str):
                    return content
                try:
                    return str(val)
                except Exception:
                    return None

            return AssistantMessage(
                content_parts=content_parts,
                tool_calls=msg_dict.get("tool_calls"),
                reasoning=_norm_reasoning(
                    msg_dict.get("reasoning", msg_dict.get("reasoning_content"))
                ),
                refusal=msg_dict.get("refusal"),
                citations=msg_dict.get("citations"),
                annotations=msg_dict.get("annotations"),
                usage=usage_data if usage_data is not None else msg_dict.get("usage"),
            )
        elif role == "user":
            return UserMessage(content_parts=content_parts)
        elif role == "system":
            return SystemMessage(content_parts=content_parts)
        elif role == "tool":
            return ToolMessage(
                content_parts=content_parts,
                tool_call_id=msg_dict.get("tool_call_id", ""),
                tool_name=msg_dict.get("tool_name", ""),
            )
        else:
            raise ValueError(f"Unsupported role for LLM response: {role}")

    def _render_part(self, part: ContentPartType, mode: RenderMode) -> str:
        """Render a single content part."""
        if isinstance(part, TemplateContentPart):
            # For RAW mode, always use the part's own render method to get raw representation
            if mode == RenderMode.RAW:
                context = self._context or {}
                return part.render(mode, context, None)

            # For other modes, use agent's template manager if available
            if self.agent is not None and self.agent.template:
                # Use centralized context resolution
                context = self.agent.get_rendering_context(self._context)

                # If the part has a context snapshot, it takes highest priority
                if part.context_snapshot:
                    context = {**context, **part.context_snapshot}

                # Add render mode to context
                context["render_mode"] = mode.value

                return self.agent.template.render_template(part.template, context)
            else:
                # Fallback for agent-less messages
                context = self._context or {}
                return part.render(mode, context, None)
        else:
            # Non-template parts
            context = self._context or {}
            return part.render(mode, context)

    def serialize_for_storage(self) -> dict[str, Any]:
        """Serialize message for storage with all content preserved."""
        # Use mode='json' to ensure JSON compatibility
        data = self.model_dump(mode="json")

        # Ensure templates have rendered cache for storage
        for i, part in enumerate(self.content_parts):
            if isinstance(part, TemplateContentPart):
                # Render for storage if not cached
                if RenderMode.STORAGE.value not in part.rendered_cache:
                    rendered = self._render_part(part, RenderMode.STORAGE)
                    part.rendered_cache[RenderMode.STORAGE.value] = rendered

                # Capture minimal context if needed
                if not part.context_snapshot and part.context_requirements:
                    part.context_snapshot = {}
                    all_context = {}
                    if self.agent is not None:
                        all_context.update(dict(self.agent.context._chainmap))
                    all_context.update(self._context)

                    for key in part.context_requirements:
                        if key in all_context:
                            # Only capture serializable values
                            value = all_context[key]
                            try:
                                import orjson

                                orjson.dumps(value)  # Test serializability
                                part.context_snapshot[key] = value
                            except (TypeError, ValueError):
                                # Store string representation
                                part.context_snapshot[key] = str(value)

                # Update serialized data
                data["content_parts"][i] = part.model_dump()

        return data

    def clear_render_cache(self) -> None:
        """Clear the render cache."""
        self._rendered_cache.clear()
        self._rendered_content = None

    @property
    def raw_content(self) -> str | None:
        """Get the raw template content before rendering."""
        # Check if we have a template content part
        for part in self.content_parts:
            if isinstance(part, TemplateContentPart):
                return part.template
        return self._raw_content

    role: MessageRole
    name: str | None = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )
    metadata: dict[str, Any] | None = None

    usage: CompletionUsage | None = None
    hidden_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Hidden parameters for internal use, not exposed to users",
    )

    @property
    def context(self) -> dict[str, Any]:
        """Get the context for template rendering."""
        return self._context

    @property
    def i(self) -> int:
        """Index of message in current iteration."""
        return self._i or 0

    @property
    def ok(self) -> bool:
        """Indicates if the message was successfully processed."""
        return self._ok

    @property
    def index(self) -> int:
        """Index of message within the agent's message list."""
        if self._agent_ref is not None:
            agent = self._agent_ref()
            if agent and hasattr(agent, "messages"):
                try:
                    return agent.messages.index(self)  # type: ignore[arg-type]
                except ValueError:
                    pass
        raise ValueError("Message not attached to agent or not found in message list")

    @property
    def attempt(self) -> int:
        """The current attempt number for this message."""
        return self._attempt

    @property
    def retry(self) -> bool:
        """Indicates if this message is a retry of a previous attempt."""
        return self._retry

    @property
    def last_attempt(self) -> bool:
        """Indicates if this is the last attempt."""
        return self._last_attempt

    @property
    def agent(self) -> Agent | None:
        """Return parent agent if available, otherwise None."""
        if self._agent_ref is not None:
            return self._agent_ref()
        return None

    def _validate_attempt(self, value: int) -> int:
        """Validate attempt number is positive."""
        if value < 1:
            raise ValueError("Attempt number must be >= 1")
        return value

    def _set_agent(self, agent: Agent) -> None:
        """Set the parent agent reference."""
        self._agent_ref = weakref.ref(agent)

    def copy_with(self, content: Any | None = None, **kwargs) -> Self:
        """Create a copy of this message with updated fields.

        Since messages are immutable, this is the way to "modify" a message.
        A new message ID will be generated.

        Args:
            content: New content for the message
            **kwargs: Fields to update

        Returns:
            New message instance with updated fields
        """
        # Get current data, excluding ID to generate a new one
        data = self.model_dump(exclude={"id"})

        # Handle content update specially - need to create new content_parts
        if content is not None:
            # Remove old content_parts and let __init__ parse the new content
            data.pop("content_parts", None)
            # Pass content to constructor
            data["content"] = content
        elif "content" in kwargs:
            data.pop("content_parts", None)
            data["content"] = kwargs.pop("content")
        elif "content_parts" in kwargs:
            # Allow direct replacement of content parts
            data["content_parts"] = kwargs.pop("content_parts")

        # Update with remaining values
        data.update(kwargs)

        if "legacy_content" not in data and "content" not in data and not data.get("content_parts"):
            data["legacy_content"] = self.render(RenderMode.DISPLAY)

        # Create new instance of the same type
        return self.__class__(**data)


# Re-export for convenience
__all__ = [
    "Message",
    "Annotation",
    "MessageRole",
    "ImageDetail",
    "IMAGE",
    "MessageContent",
]
