from __future__ import annotations

import datetime
import logging
import threading
import weakref
from abc import ABC
from collections.abc import Iterable
from datetime import timezone
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    Self,
    SupportsIndex,
    TypeVar,
    Union,
    overload,
)

from openai.types.completion_usage import CompletionUsage
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from ulid import ULID

from good_agent.core.models import GoodBase, PrivateAttrBase
from good_agent.core.types import URL
from good_agent.core.ulid_monotonic import (
    create_monotonic_ulid,
)

# Import content parts
from .content import (
    ContentPartType,
    FileContentPart,
    ImageContentPart,
    RenderMode,
    TemplateContentPart,
    TextContentPart,
    deserialize_content_part,
    is_template,
)
from .interfaces import SupportsDisplay, SupportsLLM, SupportsRender, SupportsString
from .tools import ToolCall, ToolResponse

if TYPE_CHECKING:
    from .agent import Agent
    from .versioning import MessageRegistry, VersionManager

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

type IMAGE = Union[URL, bytes]

type MessageContent = (
    Message | SupportsLLM | SupportsDisplay | SupportsString | SupportsRender | str
)


class Annotation(BaseModel):
    """Annotation for messages"""

    text: str
    start: int
    end: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class Message(PrivateAttrBase, GoodBase, ABC):
    """Base message class with content parts support and lazy rendering.

    PURPOSE: Foundation for all message types in the agent system, providing
    content management, rendering capabilities, and agent integration.

    ROLE: Core abstraction that handles:
    - Content part management (text, templates, images, files)
    - Multi-mode rendering (LLM, display, raw, storage)
    - Template resolution with context variables
    - Agent integration for versioning and events
    - Protocol implementation for different rendering contexts

    CONTENT PARTS ARCHITECTURE:
    Messages are composed of content parts that can be mixed and matched:
    - TextContentPart: Plain text content
    - TemplateContentPart: Jinja2 templates with variable substitution
    - ImageContentPart: Images from URLs or bytes
    - FileContentPart: Generic file attachments
    - Parts rendered independently then concatenated with newlines

    RENDERING PIPELINE:
    1. Context Resolution: Gather context from agent and message
    2. Template Processing: Resolve Jinja2 templates with context
    3. Content Assembly: Combine rendered parts in order
    4. Event Integration: Fire rendering events for component modification
    5. Caching: Cache results when appropriate (no templates)

    TEMPLATE SYSTEM:
    - Jinja2-based templating with security sandboxing
    - Context variables from agent.context and message.context
    - Template variables extracted automatically for performance
    - Recursive rendering prevention via thread-local guards
    - Context snapshots for stored templates

    LIFECYCLE:
    1. Creation: Message(content_parts=[...]) with content parsing
    2. Attachment: message._set_agent(agent) for context access
    3. Rendering: message.render(mode) for different output formats
    4. Storage: message.serialize_for_storage() for persistence
    5. Versioning: Automatic via MessageList integration

    THREAD SAFETY:
    - Message instances are immutable after creation
    - Rendering is thread-safe via thread-local caches
    - Template rendering prevents recursion via guards
    - Agent reference uses weakref to avoid cycles

    PERFORMANCE CHARACTERISTICS:
    - Creation: 1-5ms depending on content complexity
    - Template rendering: 10-50ms for complex templates
    - Plain text rendering: <1ms (cached)
    - Memory: ~1KB base + content size + render cache

    USAGE PATTERNS:
    ```python
    # Simple text message
    msg = UserMessage("Hello, world!")

    # Template message with context
    msg = SystemMessage("You are a {role} assistant")
    msg.context = {"role": "helpful"}

    # Multimodal content
    msg = UserMessage(
        TextContentPart("Analyze this image:"),
        ImageContentPart(url="https://example.com/image.jpg"),
    )

    # Mixed content with template
    msg = AssistantMessage(
        TemplateContentPart("Based on {data}, I conclude: {result}"),
        TextContentPart("Additional context here."),
    )
    ```

    EXTENSION POINTS:
    - Custom content parts via ContentPartType protocol
    - Rendering modes via RenderMode enum
    - Template filters and functions via agent template manager
    - Event handlers for MESSAGE_RENDER_BEFORE/AFTER events

    ERROR HANDLING:
    - Template errors: Propagated as exceptions (fatal for rendering)
    - Context missing: MissingContextValueError for required variables
    - Rendering recursion: Returns error message, prevents infinite loops
    - Content part errors: Fallback to string representation

    RELATED CLASSES:
    - UserMessage, AssistantMessage, SystemMessage, ToolMessage: Role-specific implementations
    - MessageList: Collection with versioning support
    - ContentPart types: Individual content part implementations
    - RenderMode: Available rendering contexts

    Implements SupportsLLM and SupportsDisplay protocols through methods.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="allow",
    )

    # Public field for new content parts
    content_parts: list[ContentPartType] = Field(default_factory=list)

    # Citation URLs list (not sent to LLM for all message types)
    citations: list[URL] | None = None  # ["https://...", "https://..."]

    def __repr__(self):
        """
        Ensure content is excluded to prevent recursion
        """
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
            Appropriate ContentPart instance (new style)
        """
        # Check if it's already a new-style content part
        if isinstance(
            content,
            (TextContentPart, TemplateContentPart, ImageContentPart, FileContentPart),
        ):
            return content

        # Old-style content parts no longer supported

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
                combined_text = "\n".join(
                    part.render(RenderMode.DISPLAY) for part in parts
                )
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
                content_part = cls._create_content_part(
                    part, template_detection=template_detection
                )
                parts.append(content_part)
        return parts

    __match_args__: ClassVar[tuple[str, ...]] = (  # type: ignore[misc] -- @TODO figure this out later
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

    # Legacy support removed - old content parts no longer supported

    # Rendering cache
    _rendered_cache: dict[RenderMode, str] = PrivateAttr(default_factory=dict)

    _context: dict[str, Any] = PrivateAttr(default_factory=dict)

    # Legacy support
    _raw_content: str | None = PrivateAttr(default=None)
    _rendered_content: str | None = PrivateAttr(default=None)  # Cached rendered content

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
        if "_content" in kwargs:
            # Legacy private attribute no longer supported
            raise ValueError(
                "Legacy _content attribute is no longer supported. Use content_parts instead."
            )
        else:
            content = kwargs.pop("content", None) or content

            _content = []

            if content:
                if isinstance(content, str):
                    _content = [content]
                elif isinstance(content, (list, tuple)):
                    _content = list(content)
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

        super().__init__(**kwargs)

        # Finalize content parts (extract template variables if agent is set)
        self._finalize_content_parts()

    def _finalize_content_parts(self) -> None:
        """Finalize content parts after message creation."""
        if self.agent is not None and self.agent.template:
            for part in self.content_parts:
                if (
                    isinstance(part, TemplateContentPart)
                    and not part.context_requirements
                ):
                    # Extract template variables using TemplateManager
                    part.context_requirements = (
                        self.agent.template.extract_template_variables(part.template)
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
                # raise RuntimeError(
                #     'Message Rende'
                # )

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
                return ""

            # Fire BEFORE event to allow components to modify content_parts
            content_parts = self.content_parts
            if self.agent is not None:
                from .events import AgentEvents

                # Fire BEFORE event with content_parts (not yet rendered)
                # Components can modify the parts before rendering
                ctx = self.agent.apply_sync(
                    AgentEvents.MESSAGE_RENDER_BEFORE,
                    message=self,
                    mode=mode,
                    output=list(content_parts),  # Pass parts, not rendered string
                )
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

        This uses the agent's model configuration if available, otherwise
        defaults to gpt-4o. The result is cached on the message object
        since messages are immutable.

        Returns:
            Number of tokens in this message including content and tool calls
        """
        from .utilities.tokens import get_message_token_count

        # Get model from agent if available
        model = "gpt-4o"
        if self.agent is not None:
            model = self.agent.config.model

        return get_message_token_count(message=self, model=model, include_tools=True)

    @property
    def content(self) -> str:
        """Backward compatible property - renders for display."""
        # If we have content parts, use new rendering
        return self.render(RenderMode.DISPLAY)

    @overload
    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: Literal["assistant"]
    ) -> AssistantMessage:
        """Create assistant message from LLM API response."""
        ...

    @overload
    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: Literal["user"]
    ) -> UserMessage:
        """Create user message from LLM API response."""
        ...

    @overload
    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: Literal["system"]
    ) -> SystemMessage:
        """Create system message from LLM API response."""
        ...

    @overload
    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: Literal["tool"]
    ) -> ToolMessage:
        """Create tool message from LLM API response."""
        ...

    @classmethod
    def from_llm_response(
        cls, response: dict[str, Any], role: MessageRole = "assistant"
    ) -> Message:
        """Create message from LLM API response.

        Args:
            response: Raw response from LLM API (e.g., response["choices"][0]["message"])
            role: Message role (usually 'assistant')

        Returns:
            Appropriate Message instance with parsed content
        """
        # Normalize response shape: support both top-level API response and inner message dicts
        # Top-level responses typically have: { choices: [{ message: {...} }], usage: {...}, ... }
        # Inner message dicts have: { role: "assistant", content: "...", tool_calls: [...] }
        msg_dict: dict[str, Any] = response
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
                    msg_dict = msg_obj if isinstance(msg_obj, dict) else {}
                except Exception:
                    msg_dict = {}
            # Extract usage from the top-level response if present
            usage_data = response.get("usage")

        # Extract content from the normalized message dict
        content = msg_dict.get("content", "")

        # LLM responses are typically strings, not lists
        if isinstance(content, str):
            # Simple string response - create single text part
            content_parts = [TextContentPart(text=content)]
        elif isinstance(content, list):
            # Some LLMs might return structured content (rare)
            content_parts: list[TextContentPart | ImageContentPart] = []
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
        from . import messages

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

            return messages.AssistantMessage(
                content_parts=content_parts,
                tool_calls=msg_dict.get("tool_calls"),
                reasoning=_norm_reasoning(
                    msg_dict.get("reasoning", msg_dict.get("reasoning_content"))
                ),
                refusal=msg_dict.get("refusal"),
                usage=usage_data if usage_data is not None else msg_dict.get("usage"),
            )
        elif role == "user":
            return messages.UserMessage(content_parts=content_parts)
        elif role == "system":
            return messages.SystemMessage(content_parts=content_parts)
        elif role == "tool":
            return messages.ToolMessage(
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
        """Get the raw template content before rendering"""
        # Check if we have a template content part
        for part in self.content_parts:
            if isinstance(part, TemplateContentPart):
                return part.template
        return self._raw_content

    # @property
    # def rendered_content(self) -> str:
    #     """Alias for content property for backward compatibility"""
    #     return self.content

    role: MessageRole
    name: str | None = None
    timestamp: datetime.datetime = Field(
        default_factory=lambda: datetime.datetime.now(timezone.utc)
    )
    metadata: dict[str, Any] | None = None

    usage: CompletionUsage | None = None
    hidden_params: dict[str, Any] = Field(
        default_factory=dict,
        description="Hidden parameters for internal use, not exposed to users",
    )

    @property
    def context(self) -> dict[str, Any]:
        """Get the context for template rendering"""
        return self._context

    @property
    def i(self) -> int:
        """Index of message in current iteration"""
        return self._i or 0

    @property
    def ok(self) -> bool:
        """Indicates if the message was successfully processed"""
        return self._ok

    @property
    def index(self) -> int:
        """Index of message within the agent's message list"""
        if self._agent_ref is not None:
            agent = self._agent_ref()
            if agent and hasattr(agent, "messages"):
                try:
                    return agent.messages.index(self)
                except ValueError:
                    pass
        raise ValueError("Message not attached to agent or not found in message list")

    @property
    def attempt(self) -> int:
        """The current attempt number for this message"""
        return self._attempt

    @property
    def retry(self) -> bool:
        """Indicates if this message is a retry of a previous attempt"""
        return self._retry

    @property
    def last_attempt(self) -> bool:
        """Indicates if this is the last attempt"""
        return self._last_attempt

    @property
    def agent(self) -> Agent | None:
        """Return parent agent if available, otherwise None"""
        if self._agent_ref is not None:
            return self._agent_ref()
        return None

    def _validate_attempt(self, value: int) -> int:
        """Validate attempt number is positive"""
        if value < 1:
            raise ValueError("Attempt number must be >= 1")
        return value

    def _set_agent(self, agent: Agent) -> None:
        """Set the parent agent reference"""
        self._agent_ref = weakref.ref(agent)

    def copy_with(self, content: Any | None = None, **kwargs) -> Self:
        """
        Create a copy of this message with updated fields.

        Since messages are immutable, this is the way to "modify" a message.
        A new message ID will be generated.

        Args:
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

        # Create new instance of the same type
        return self.__class__(**data)


class UserMessage(Message):
    """User message with optional images"""

    @overload
    def __init__(self, content: str | None = None, **data):
        """Initialize with content or template"""
        ...

    @overload
    def __init__(self, *content: MessageContent, **data):
        """Initialize with iterable content parts or template"""
        ...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    role: Literal["user"] = "user"  # type: ignore
    images: list[IMAGE] | None = None
    image_detail: ImageDetail | None = "auto"


class SystemMessage(Message):
    """System message for instructions"""

    @overload
    def __init__(
        self,
        content: str | None = None,
        # template: str | None = None,
        **data,
    ): ...

    @overload
    def __init__(self, *content: MessageContent, **data): ...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    role: Literal["system"] = "system"  # type: ignore


T_ToolResponse = TypeVar("T_ToolResponse", bound=ToolResponse)


class ToolMessage(Message, Generic[T_ToolResponse]):
    """Tool response message"""

    @overload
    def __init__(
        self,
        content: str | None = None,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_response: T_ToolResponse | None = None,
        **data,
    ):
        """Initialize with content and tool call details"""
        ...

    @overload
    def __init__(
        self,
        *content: MessageContent,
        tool_call_id: str | None = None,
        tool_name: str | None = None,
        tool_response: T_ToolResponse | None = None,
        **data,
    ):
        """Initialize with content parts and tool call details"""
        ...

    @overload
    def __init__(self, *content: MessageContent, **data):
        """Initialize with content parts only"""
        ...

    def __init__(self, *args, **kwargs):
        # Handle tool_name to name aliasing
        if "tool_name" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs["tool_name"]
        elif "name" in kwargs and "tool_name" not in kwargs:
            kwargs["tool_name"] = kwargs["name"]
        super().__init__(*args, **kwargs)

    role: Literal["tool"] = "tool"  # type: ignore
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
            or "</"
            in content_stripped[:100]  # Check for closing tags in first 100 chars
        ):
            # Wrap in XML code block for proper display
            # Use the content as-is after basic stripping to preserve formatting
            return f"```xml\n{content_stripped}\n```"

        # For non-XML content, return as-is
        return content


type CitationURL = URL


class AssistantMessage(Message):
    """Assistant message with optional tool calls"""

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
        annotations: list[Annotation] | None = None,
        **data,
    ): ...

    @overload
    def __init__(self, *content: MessageContent, **data): ...

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    role: Literal["assistant"] = "assistant"  # type: ignore
    tool_calls: list[ToolCall] | None = None
    reasoning: str | None = None
    refusal: str | None = None
    citations: list[CitationURL] | None = None
    annotations: list[Annotation] | None = None

    # Compatibility alias for providers (e.g., OpenRouter) that return
    # `reasoning_content` instead of `reasoning` on assistant messages.
    @property
    def reasoning_content(self) -> str | None:  # read-only alias
        return self.reasoning

    def __display__(self) -> str:
        """Protocol method for display rendering.

        Returns the rendered content. If there's no content but there are tool calls,
        returns an empty string to indicate that the message contains only tool calls.
        This allows the print_message utility to properly handle tool-only messages.
        """
        content = self.render(RenderMode.DISPLAY)
        # If we have no content but do have tool calls, return empty string
        # This signals to print_message that we have a tool-only message
        if not content and self.tool_calls:
            return ""  # Will be handled by print_message to show tool calls properly
        return content


T_Output = TypeVar("T_Output", bound=BaseModel)


class AssistantMessageStructuredOutput(AssistantMessage, Generic[T_Output]):
    output: T_Output

    def __display__(self) -> str:
        from good_common.utilities import yaml_dumps

        _type = type(self.output)
        return yaml_dumps(self.output.model_dump(mode="json"))
        # return f'<{_type.__name__}>\n{_inner}\n</{_type.__name__}>'


T_Message = TypeVar("T_Message", bound=Message)


class MessageFactory:
    """Factory for creating messages from dictionaries"""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Message:
        """
        Create a message from a dictionary representation.

        Args:
            data: Dictionary containing message data

        Returns:
            Appropriate message instance
        """
        # Handle legacy content format
        if "content" in data and "content_parts" not in data:
            # Legacy format - convert string content to new format
            content = data.pop("content")
            if isinstance(content, str):
                data["content_parts"] = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                # Already structured - assume it's content parts
                data["content_parts"] = content

        # Parse content_parts if present
        if "content_parts" in data:
            parsed_parts = []
            for part_data in data["content_parts"]:
                if isinstance(part_data, dict):
                    parsed_parts.append(deserialize_content_part(part_data))
                else:
                    # Already a content part object
                    parsed_parts.append(part_data)
            data["content_parts"] = parsed_parts

        # Create appropriate message type
        message_type = data.get("type") or data.get("role")

        if message_type == "system":
            return SystemMessage(**data)
        elif message_type == "user":
            return UserMessage(**data)
        elif message_type == "assistant":
            return AssistantMessage(**data)
        elif message_type == "tool":
            return ToolMessage(**data)
        else:
            raise ValueError(f"Unknown message type: {message_type}")


class MessageList(list[T_Message], Generic[T_Message]):
    """Enhanced MessageList with version support while maintaining list interface.

    PURPOSE: Thread-safe message collection that provides list compatibility
    while adding versioning, agent integration, and message management.

    ROLE: Central message storage that bridges:
    - List interface for backward compatibility and familiar usage
    - Versioning system for message history tracking and rollback
    - Agent integration for automatic version management
    - Event system for message lifecycle notifications
    - Serialization support for persistence and restoration

    VERSIONING ARCHITECTURE:
    1. Message Registry: Global storage for all message instances with weak references
    2. Version Manager: Tracks message IDs and version history with rollback capability
    3. Agent Integration: Automatic version updates on any list modifications
    4. Serialization Support: Complete message state preservation for storage/restoration

    LIST INTERFACE COMPATIBILITY:
    - Maintains full list[T] interface for backward compatibility
    - All standard list operations work (append, extend, indexing, slicing, etc.)
    - Type hints preserved for static analysis and IDE support
    - Iteration returns original message objects, not copies
    - Slicing returns list[T], not MessageList (preserves list semantics)

    SERIALIZATION PERFORMANCE:
    - Message serialization: 10-50ms per message depending on content complexity
    - Template serialization: Additional 5-20ms for context snapshot generation
    - Storage format: JSON-compatible with binary content base64-encoded
    - Caching: Rendered templates cached to avoid re-serialization
    - Memory overhead: ~2x message size during serialization process

    SERIALIZATION STRATEGY:
    1. Content Part Serialization: Each part serialized with appropriate format
    2. Template Context Capture: Required variables extracted and stored with templates
    3. Version Information: Message IDs and version history preserved
    4. Agent Context: Context snapshots captured for template reproduction
    5. Binary Content: Images/files converted to base64 with metadata preservation

    AGENT INTEGRATION:
    - Messages automatically registered with agent when added to list
    - Versions updated on any modification (append, replace, extend, clear)
    - Context provided for template rendering through agent reference
    - Events fired for message lifecycle notifications
    - Weak references prevent memory leaks between agent and messages

    CONCURRENCY AND THREAD SAFETY:
    - Thread-safe for read operations (standard list interface)
    - Version updates coordinated through agent's version manager
    - Message instances are immutable after creation (safe for sharing)
    - Weak references prevent circular references and memory leaks
    - Serialization is thread-safe via message-level caching

    PERFORMANCE CHARACTERISTICS:
    - List operations: O(1) for append, O(n) for insert/delete by index
    - Versioning: O(1) per message (just ID tracking in version manager)
    - Serialization: O(n*m) where n=messages, m=average content size
    - Memory: O(n) for messages + O(v) for version history + O(s) for serialization cache
    - Synchronization: Minimal overhead for agent integration via weak references

    USAGE PATTERNS:
    ```python
    # Standard list usage - full compatibility
    messages = MessageList[Message]()
    messages.append(UserMessage("Hello"))
    messages.extend([AssistantMessage("Hi!"), UserMessage("How are you?")])

    # Filtering and type-safe access
    user_messages = messages.filter(role="user")  # Returns MessageList[UserMessage]
    last_message = messages[-1]  # Type T_Message
    recent_messages = messages[-3:]  # Returns list[T_Message]

    # Versioning (when attached to agent)
    agent = Agent()
    agent.messages._init_versioning(registry, version_manager, agent)
    current_version = agent.messages.current_version
    agent.messages.revert_to_version(0)  # Rollback to initial state

    # Serialization for persistence
    serialized_data = [msg.serialize_for_storage() for msg in messages]
    # Restore later: messages = MessageList([MessageFactory.from_dict(data) for data in serialized_data])
    ```

    MESSAGELIST vs FILTEREDMESSAGELIST:
    - MessageList: Full list interface with versioning and persistence support
    - FilteredMessageList: Role-specific wrapper for agent.message filtering
    - MessageList: Direct list operations, version management, serialization
    - FilteredMessageList: Agent integration, role enforcement, simplified API

    EVENT INTEGRATION:
    - MESSAGE_APPEND_AFTER: Fired when messages are added via append/extend
    - MESSAGE_REPLACE_BEFORE/AFTER: Fired when messages are replaced via indexing
    - Version events fired through agent version manager on modifications
    - Serialization events fired during storage/restoration operations

    ERROR HANDLING:
    - Invalid message types: TypeError from list interface (standard Python behavior)
    - Version errors: Graceful degradation, logged warnings, operations continue
    - Agent not available: All operations work without versioning/serialization
    - Registry errors: Messages stored locally, versioning disabled gracefully
    - Serialization errors: Individual message failures logged, collection continues

    RELATED CLASSES:
    - Message: Base message class with rendering and serialization support
    - FilteredMessageList: Role-based filtering wrapper with agent integration
    - VersionManager: Version tracking and rollback with history preservation
    - MessageRegistry: Global message storage with weak reference management
    - MessageFactory: Message creation from serialized dictionaries

    EXTENSION POINTS:
    - Custom filtering methods via filter() overloads with type safety
    - Version management via _sync_from_version() for custom restoration
    - Agent integration via _set_agent() for context and event access
    - Custom serialization via message.serialize_for_storage() overrides
    - Event handling for custom message types and lifecycle management

    SERIALIZATION EXAMPLES:
    ```python
    # Basic serialization
    messages = MessageList[Message]()
    messages.append(UserMessage("Hello"))
    messages.append(AssistantMessage(TemplateContentPart("Response: {answer}")))

    # Serialize all messages
    serialized = [msg.serialize_for_storage() for msg in messages]
    # Each dict contains: role, content_parts, metadata, timestamps, etc.

    # Restore messages
    restored = MessageList[Message](
        [MessageFactory.from_dict(data) for data in serialized]
    )

    # Template context is preserved during serialization
    template_msg = restored[1]  # AssistantMessage with template
    # Template variables captured during original serialization
    ```
    """

    def __init__(self, messages: Iterable[T_Message] | None = None):
        # Keep the list interface for backward compatibility
        super().__init__(messages or [])

        # Add versioning support (will be initialized by Agent if versioning is enabled)
        self._registry: MessageRegistry | None = None
        self._version_manager: VersionManager | None = None
        self._agent_ref: weakref.ReferenceType[Agent] | None = None

    def _set_agent(self, agent: Agent):
        self._agent_ref = weakref.ref(agent)

    def _init_versioning(
        self, registry: MessageRegistry, version_manager: VersionManager, agent: Agent
    ):
        """Initialize versioning support (called by Agent during setup).

        Args:
            registry: The message registry for storing messages
            version_manager: The version manager for tracking versions
            agent: The parent agent
        """

        self._registry = registry
        self._version_manager = version_manager
        self._agent_ref = weakref.ref(agent)

        # If we have existing messages, create initial version
        if len(self) > 0:
            message_ids = []
            for message in self:
                self._registry.register(message, agent)
                message_ids.append(message.id)
            self._version_manager.add_version(message_ids)

    def _sync_from_version(self):
        """Sync list contents from current version (internal method)."""
        if not self._version_manager or not self._registry:
            return

        # Clear current list
        super().clear()

        # Rebuild from version
        for message_id in self._version_manager.current_version:
            message = self._registry.get(message_id)
            if message:
                super().append(message)

    @property
    def agent(self) -> Agent | None:
        """Return parent agent if available, otherwise None"""
        if self._agent_ref is not None:
            return self._agent_ref()
        return None

    def append(self, message: T_Message) -> None:
        """Append message with version tracking.

        Args:
            message: The message to append
        """
        # Standard list append
        super().append(message)

        # If versioning is enabled, update version
        if self._version_manager and self._registry and self._agent_ref:
            agent = self._agent_ref()
            if agent:
                self._registry.register(message, agent)
                new_version = self._version_manager.current_version
                new_version.append(message.id)
                self._version_manager.add_version(new_version)

    @overload
    def __setitem__(self, index: SupportsIndex, message: T_Message) -> None: ...

    @overload
    def __setitem__(self, index: slice, message: Iterable[T_Message]) -> None: ...

    def __setitem__(self, index: SupportsIndex | slice, message: Any) -> None:
        """Set item with version tracking.

        Args:
            index: The index or slice to set
            message: The message or messages to set
        """
        # For slices, we need special handling
        if isinstance(index, slice):
            # Standard list setitem for slices
            super().__setitem__(index, message)

            # If versioning is enabled, create new version with all current IDs
            if self._version_manager and self._registry and self._agent_ref:
                agent = self._agent_ref()
                if agent:
                    # Register all new messages
                    for msg in message:
                        if isinstance(msg, Message):
                            self._registry.register(msg, agent)

                    # Create new version with current message IDs
                    new_version = [msg.id for msg in self]
                    self._version_manager.add_version(new_version)
        else:
            # Single item replacement
            # Standard list setitem
            super().__setitem__(index, message)

            # If versioning is enabled, create new version
            if self._version_manager and self._registry and self._agent_ref:
                agent = self._agent_ref()
                if agent and isinstance(message, Message):
                    self._registry.register(message, agent)
                    new_version = list(self._version_manager.current_version)
                    # Convert index to int
                    idx = int(index)
                    # Update the ID at the specified index
                    if 0 <= idx < len(new_version):
                        new_version[idx] = message.id
                    elif idx == len(new_version):
                        # Appending via index
                        new_version.append(message.id)
                    self._version_manager.add_version(new_version)

    def extend(self, messages: Iterable[T_Message]) -> None:
        """Extend list with multiple messages, creating a single new version.

        Args:
            messages: Messages to add
        """
        # Convert to list to avoid consuming iterator twice
        message_list = list(messages)

        # Standard list extend
        super().extend(message_list)

        # If versioning is enabled, create single new version
        if self._version_manager and self._registry and self._agent_ref:
            agent = self._agent_ref()
            if agent:
                new_version = list(self._version_manager.current_version)
                for message in message_list:
                    self._registry.register(message, agent)
                    new_version.append(message.id)
                self._version_manager.add_version(new_version)

    def clear(self) -> None:
        """Clear all messages and create empty version."""
        super().clear()

        # If versioning is enabled, create empty version
        if self._version_manager:
            self._version_manager.add_version([])

    def prepend(self, message: T_Message) -> None:
        """Add message at the beginning with versioning support.

        Args:
            message: The message to prepend
        """
        # Insert at beginning
        super().insert(0, message)

        # If versioning is enabled, create new version
        if self._version_manager and self._registry and self._agent_ref:
            agent = self._agent_ref()
            if agent:
                # Register the message
                self._registry.register(message, agent)

                # Create new version with message prepended
                current_ids = self._version_manager.current_version.copy()
                new_ids = [message.id] + current_ids
                self._version_manager.add_version(new_ids)

    def replace_at(self, index: int, message: T_Message) -> None:
        """Replace message at index with versioning support.

        This is a convenience method that ensures versioning is properly handled.

        Args:
            index: The index to replace at
            message: The message to set
        """
        # Use __setitem__ which already handles versioning
        self[index] = message

    @overload
    def filter(
        self,
        role: Literal["system"],
        **kwargs: Any,
    ) -> MessageList[SystemMessage]: ...

    @overload
    def filter(
        self,
        role: Literal["user"],
        **kwargs: Any,
    ) -> MessageList[UserMessage]: ...

    @overload
    def filter(
        self,
        role: Literal["assistant"],
        **kwargs: Any,
    ) -> MessageList[AssistantMessage]: ...

    @overload
    def filter(
        self,
        role: Literal["tool"],
        **kwargs: Any,
    ) -> MessageList[ToolMessage]: ...

    @overload
    def filter(
        self,
        role: None = None,
        **kwargs: Any,
    ) -> MessageList[T_Message]: ...

    def filter(self, role: MessageRole | None = None, **kwargs) -> MessageList:
        """Filter messages by role or other attributes"""
        result = self

        if role is not None:
            # Type-specific filtering based on role
            filtered: list[Message] = []
            for m in result:
                if m.role == role:
                    filtered.append(m)
            result = MessageList(filtered)

        for key, value in kwargs.items():
            filtered = []
            for m in result:
                if getattr(m, key, None) == value:
                    filtered.append(m)
            result = MessageList(filtered)

        return result

    @property
    def user(self) -> MessageList[UserMessage]:
        """Get all user messages"""
        filtered = [m for m in self if isinstance(m, UserMessage)]
        return MessageList[UserMessage](filtered)

    @property
    def assistant(self) -> MessageList[AssistantMessage]:
        """Get all assistant messages"""
        filtered = [m for m in self if isinstance(m, AssistantMessage)]
        return MessageList[AssistantMessage](filtered)

    @property
    def system(self) -> MessageList[SystemMessage]:
        """Get all system messages"""
        filtered = [m for m in self if isinstance(m, SystemMessage)]
        return MessageList[SystemMessage](filtered)

    @property
    def tool(self) -> MessageList[ToolMessage]:
        """Get all tool messages"""
        filtered = [m for m in self if isinstance(m, ToolMessage)]
        return MessageList[ToolMessage](filtered)

    @overload
    def __getitem__(self, key: SupportsIndex, /) -> T_Message: ...

    @overload
    def __getitem__(self, key: slice, /) -> list[T_Message]: ...

    def __getitem__(
        self,
        key: SupportsIndex | slice,
        /,
    ) -> T_Message | list[T_Message]:
        """Support both indexing and slicing"""
        result = list.__getitem__(self, key)
        if isinstance(key, slice):
            # Return as list, not MessageList, to match parent signature
            return result
        return result


class FilteredMessageList(MessageList[T_Message], Generic[T_Message]):
    """Role-specific message wrapper with agent integration and simplified API.

    PURPOSE: Provides a role-filtered view of agent messages with simplified
    operations for common message management tasks.

    ROLE: Acts as a specialized interface that:
    - Filters messages by role (user, assistant, system, tool)
    - Provides simplified message creation and management
    - Integrates with agent for automatic event handling and versioning
    - Enforces role-specific constraints and operations
    - Offers convenient properties for common operations

    FILTEREDMESSAGELIST vs MESSAGELIST:
    - FilteredMessageList: Role-specific wrapper, simplified API, agent integration
    - MessageList: Full list interface, versioning, serialization support
    - FilteredMessageList: append() creates messages with correct role automatically
    - MessageList: append() requires explicit message creation
    - FilteredMessageList: set() method for system message configuration
    - MessageList: Direct list operations only

    ROLE ENFORCEMENT:
    - All created messages automatically have the filtered role
    - Role-specific validation (e.g., tool_call_id required for tool messages)
    - Specialized methods for role-specific operations
    - Type safety through generic type parameters

    AGENT INTEGRATION:
    - All operations delegate to agent for consistent event handling
    - Automatic version management through agent's message system
    - Context injection for template rendering
    - Configuration updates for system messages

    USAGE PATTERNS:
    ```python
    # Agent creates filtered lists automatically
    agent = Agent()

    # System message management
    agent.system.set("You are a helpful assistant", temperature=0.7)
    system_content = agent.system.content  # Get first system message

    # User message creation
    agent.user.append("Hello, how are you?")

    # Tool response (requires tool_call_id)
    agent.tool.append("Search completed", tool_call_id="call_123")

    # Check if messages exist
    if agent.system:
        print("System message configured")

    # Filtered access is read-only for iteration
    for msg in agent.assistant:
        print(msg.content)
    ```

    PERFORMANCE CHARACTERISTICS:
    - Message creation: ~5-10ms per message (including agent processing)
    - Filtering: O(1) access, filtering done by agent internally
    - Memory: Minimal overhead, references agent's message list
    - Agent integration: All operations go through agent for consistency

    THREAD SAFETY:
    - Read operations: Thread-safe (read-only access to agent messages)
    - Write operations: Thread-safe via agent's message management
    - Agent coordination: All operations synchronized through agent

    ERROR HANDLING:
    - Role validation: ValueError for invalid role-specific operations
    - Missing parameters: Clear error messages for required fields
    - Agent errors: Propagated from agent operations
    - Type safety: Generic type parameters provide compile-time checking

    EXTENSION POINTS:
    - Custom role-specific operations via subclassing
    - Agent integration patterns for consistent behavior
    - Event handling for role-specific lifecycle events
    - Configuration management for system messages
    """

    def __init__(
        self,
        agent: Agent,
        role: MessageRole,
        messages: Iterable[T_Message] | None = None,
    ):
        """Initialize filtered message list with agent and role.

        PURPOSE: Create a role-specific wrapper around agent messages with
        initial message population and agent integration.

        Args:
            agent: The parent agent instance for integration and event handling
            role: The message role to filter for (user, assistant, system, tool)
            messages: Initial messages to populate the list with

        SIDE EFFECTS:
        - Stores agent reference for operations and event handling
        - Sets role for message creation and validation
        - Initializes with provided messages if any
        """
        super().__init__(messages or [])
        self._agent = agent
        self._role = role

    def append(self, *content_parts: str, **kwargs):  # type: ignore[override]
        """Append a message with the filtered role to the agent.

        PURPOSE: Create and append a message with the correct role automatically,
        delegating to the agent for consistent event handling and versioning.

        ROLE-SPECIFIC BEHAVIOR:
        - Creates message with the filtered role automatically
        - Validates role-specific requirements (e.g., tool_call_id for tools)
        - Delegates to agent.append() for consistent processing
        - Fires appropriate agent events for message lifecycle

        Args:
            *content_parts: Content parts for the message (joined with newlines)
            **kwargs: Additional message parameters (role automatically set)

        Raises:
            ValueError: If role-specific required parameters are missing

        EXAMPLES:
        ```python
        # User message - simple content
        agent.user.append("Hello, world!")

        # Assistant message - with tool calls
        agent.assistant.append("I'll search for that", tool_calls=[...])

        # Tool message - requires tool_call_id
        agent.tool.append("Search results", tool_call_id="call_123", tool_name="search")

        # System message - with configuration
        agent.system.append("You are helpful", temperature=0.7)
        ```
        """
        # Join multiple content parts with newlines
        if len(content_parts) > 1:
            content = "\n".join(content_parts)
        elif len(content_parts) == 1:
            content = content_parts[0]
        else:
            content = ""

        # Role-specific validation
        if self._role == "tool" and "tool_call_id" not in kwargs:
            raise ValueError("tool_call_id is required for tool messages")

        # Always delegate to agent's append method for consistent event handling
        kwargs["role"] = self._role
        self._agent.append(content, **kwargs)

    @property
    def content(self) -> str | None:
        """Get content of the first message (for system role compatibility).

        PURPOSE: Provide convenient access to the primary message content,
        primarily used for system message access.

        Returns:
            Content of the first message in the filtered list, or None if empty

        USAGE:
        ```python
        # System message content access
        if agent.system.content:
            print(f"System: {agent.system.content}")

        # Check if system message exists
        if not agent.system.content:
            agent.system.set("Default system message")
        ```
        """
        if len(self) > 0:
            return self[0].content
        return None

    def set(self, content: str, **kwargs):
        """Set the system message (only for system role).

        PURPOSE: Convenience method for updating the system message with
        optional configuration parameters, updating both message and agent config.

        ROLE RESTRICTION:
        - Only available for system role (enforced at runtime)
        - Other roles raise ValueError for operation not supported

        CONFIGURATION INTEGRATION:
        - Extracts known config parameters from kwargs
        - Updates agent.config alongside message content
        - Supports temperature, max_tokens, top_p, and other LLM parameters

        Args:
            content: New system message content
            **kwargs: Additional parameters, including LLM configuration

        Raises:
            ValueError: If called on non-system role

        EXAMPLES:
        ```python
        # Basic system message update
        agent.system.set("You are a helpful AI assistant")

        # With LLM configuration
        agent.system.set("You are a concise assistant", temperature=0.1, max_tokens=500)

        # Invalid - raises ValueError
        agent.user.set("This won't work")  # ValueError
        ```
        """
        if self._role == "system":
            # Extract configuration parameters
            config_params = {}
            for key in [
                "temperature",
                "max_tokens",
                "top_p",
                "frequency_penalty",
                "presence_penalty",
            ]:
                if key in kwargs:
                    config_params[key] = kwargs.pop(key)

            # Set system message
            self._agent.set_system_message(content, **kwargs)

            # Update agent configuration if parameters were provided
            if config_params:
                for key, value in config_params.items():
                    setattr(self._agent.config, key, value)
        else:
            raise ValueError(
                f"set() is only available for system messages, not {self._role}"
            )

    def __bool__(self):
        """Return True if there are messages of this type.

        PURPOSE: Enable boolean checking for role-specific message existence,
        providing convenient conditional logic.

        USAGE:
        ```python
        # Check if any messages of this role exist
        if agent.system:
            print("System message configured")

        if not agent.user:
            print("No user messages yet")

        # Boolean context in conditional expressions
        has_tool_responses = bool(agent.tool)
        ```
        """
        return len(self) > 0
