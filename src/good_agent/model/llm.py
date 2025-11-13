import asyncio
import copy

# Lazy loading imports - moved to TYPE_CHECKING
import logging
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    TypedDict,
    TypeVar,
    Unpack,
    cast,
    overload,
    runtime_checkable,
)

from pydantic import BaseModel

from good_agent.core.types import URL

from ..components import AgentComponent
from ..config import AgentConfigManager
from ..config_types import PASS_THROUGH_KEYS, ModelConfig
from ..content import (
    ContentPartType,
    FileContentPart,
    ImageContentPart,
    RenderMode,
    TemplateContentPart,
    TextContentPart,
)
from ..events import AgentEvents
from ..messages import (
    AssistantMessage,
    AssistantMessageStructuredOutput,
    Message,
    MessageContent,
    MessageRole,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from ..utilities import url_to_base64

# Lazy loading ManagedRouter - moved to property
from .manager import ManagedRouter, ModelManager
from .overrides import model_override_registry

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from litellm.types.completion import (
        ChatCompletionMessageParam,
    )
    from litellm.types.utils import Choices, ModelResponse, StreamingChoices, Usage


class ModelResponseProtocol(Protocol):
    """Protocol for model response objects with usage"""

    @property
    def id(self) -> str: ...

    @property
    def choices(self) -> "Choices | StreamingChoices": ...

    @property
    def model(self) -> str | Any: ...

    @property
    def created(self) -> int: ...


@runtime_checkable
class ResponseWithUsage(Protocol):
    @property
    def usage(self) -> "Usage | None": ...


@runtime_checkable
class ResponseWithHiddenParams(Protocol):
    @property
    def _hidden_params(self) -> dict[str, Any] | Any: ...


@runtime_checkable
class ResponseWithResponseHeaders(ModelResponseProtocol, Protocol):
    @property
    def _response_headers(self) -> dict[str, Any] | Any: ...


type ModelName = str


# class EventCompletion(TypedDict):
#     messages: Sequence["ChatCompletionMessageParam | dict[str, Any]"]
#     config: ModelConfig


class CompletionEvent(TypedDict):
    """Event type for chat completion without response model extraction."""

    messages: list["ChatCompletionMessageParam"]
    config: ModelConfig
    response_model: type[BaseModel] | None
    llm: "LanguageModel"


# class AfterCompletionEvent(BeforeCompletionEvent):
#     """Event type for completion with response model extraction."""
#     messages: Sequence[dict[str, Any]]
#     config: dict[str, Any]
#     response_model: type[BaseModel]
#     llm: "LanguageModel"


@dataclass
class StreamChunk:
    """Streaming response chunk"""

    content: str | None = None
    finish_reason: str | None = None


DEFAULT_MODEL = "gpt-4.1-mini"
LLM_DEFAULTS = ModelConfig(model=DEFAULT_MODEL, debug=False)

FILTER_ARGS = [
    "instructor_mode",
    "context",
    "max_retries",
    "fallback_models",
    "debug",
]


DEFAULT_TEMPERATURE = 1
# DEFAULT_TOP_P = 1.0


CACHE_DIR = Path("~/.good-intel/cache").expanduser()


T_Message = TypeVar("T_Message", bound=Message)


class LanguageModel(AgentComponent):
    """PURPOSE: Core LLM abstraction providing unified interface for multi-provider language models.

    PURPOSE: Orchestrates LLM interactions with comprehensive support for:
    - Multi-provider routing via litellm abstraction layer
    - Structured output extraction via instructor integration
    - Automatic retry and fallback model management
    - Model capability detection and parameter validation
    - Message formatting and content transformation
    - Token usage tracking and cost calculation

    ROLE: Central coordinator for all LLM operations in the agent system:
    - Manages model configuration and provider-specific settings
    - Handles message formatting between internal and LLM API formats
    - Provides capability detection for features like function calling, vision, etc.
    - Tracks usage statistics and implements retry/fallback strategies
    - Integrates with event system for lifecycle monitoring

    LIFECYCLE:
    1. Creation: LanguageModel(**config) creates instance with model settings
    2. Initialization: Lazy loading of ManagedRouter and instructor on first use
    3. Configuration: Model overrides applied, capabilities detected, routing setup
    4. Operation: complete(), extract(), or stream() methods handle LLM interactions
    5. Monitoring: Usage tracking, event emission, error handling throughout

    THREAD SAFETY: NOT thread-safe. Each LanguageModel instance should be used by
    only one async task at a time. Multiple instances can be used concurrently
    with isolated callback handling via ManagedRouter.

    TYPICAL USAGE:
    ```python
    # Basic usage with default configuration
    llm = LanguageModel(model="gpt-4", temperature=0.7)
    response = await llm.complete(messages)

    # With fallback models and structured output
    llm = LanguageModel(model="gpt-4", fallback_models=["gpt-3.5-turbo"], max_retries=3)
    structured_response = await llm.extract(messages, response_model=MySchema)

    # Streaming responses
    async for chunk in llm.stream(messages):
        print(chunk.content, end="", flush=True)
    ```

    STATE MANAGEMENT:
    - Maintains usage statistics: total_tokens, total_cost, last_usage, last_cost
    - Tracks API requests/responses for debugging: api_requests, api_responses
    - Manages internal state for instructor and router initialization
    - Preserves request history in api_errors for error analysis

    ERROR HANDLING:
    - API failures: Automatic retry with exponential backoff and fallback models
    - Model capability mismatches: Parameter filtering and validation
    - Configuration errors: Model override application with graceful fallback
    - Network timeouts: Configurable timeout handling with retry logic
    - Structured output failures: Instructor validation with detailed error messages

    PERFORMANCE OPTIMIZATIONS:
    - Lazy loading of litellm types and instructor to reduce startup overhead
    - Model-specific parameter filtering to avoid unnecessary API calls
    - Efficient message formatting with content caching where possible
    - Connection pooling and reuse via ManagedRouter
    - Token usage tracking for cost optimization

    EXTENSION POINTS:
    - Custom model registration via register_model_override()
    - Event hooks for monitoring LLM lifecycle events
    - Custom capability detection through model override system
    - Integration with external monitoring via callback system
    - Model-specific parameter transformation pipelines

    INTEGRATION PATTERNS:
    - Event-driven: Emits LLM_COMPLETE_BEFORE/AFTER, LLM_EXTRACT_BEFORE/AFTER, etc.
    - Configuration-driven: Uses AgentConfigManager for centralized settings
    - Retry-aware: Automatic fallback model routing with configurable strategies
    - Type-safe: Full typing support with overloaded methods and protocols
    - Resource-managed: Automatic cleanup and connection pooling

    RELATED CLASSES:
    - ManagedRouter: Isolated callback handling and retry logic
    - ModelOverride: Model-specific parameter customization
    - AgentComponent: Base class providing event system integration
    - StreamChunk: Streaming response container with metadata
    - ModelConfig: Typed configuration dictionary for LLM parameters
    """

    # Class-level cache for lazy-loaded litellm types
    _litellm_types_cache: dict[str, Any] = {}

    # Class-level ModelManager for shared model registration
    _model_manager = ModelManager()

    @classmethod
    def _get_litellm_type(cls, type_name: str) -> Any:
        """Lazy-load litellm types only when needed."""
        if type_name not in cls._litellm_types_cache:
            if type_name == "ChatCompletionContentPartTextParam":
                from litellm.types.completion import ChatCompletionContentPartTextParam

                cls._litellm_types_cache[type_name] = ChatCompletionContentPartTextParam
            elif type_name == "ChatCompletionContentPartImageParam":
                from litellm.types.completion import ChatCompletionContentPartImageParam

                cls._litellm_types_cache[type_name] = (
                    ChatCompletionContentPartImageParam
                )
            elif type_name == "ImageURL":
                from litellm.types.completion import ImageURL

                cls._litellm_types_cache[type_name] = ImageURL
            elif type_name == "ChatCompletionFileObject":
                from litellm.types.llms.openai import ChatCompletionFileObject

                cls._litellm_types_cache[type_name] = ChatCompletionFileObject
            elif type_name == "ChatCompletionFileObjectFile":
                from litellm.types.llms.openai import ChatCompletionFileObjectFile

                cls._litellm_types_cache[type_name] = ChatCompletionFileObjectFile
            elif type_name == "ChatCompletionSystemMessageParam":
                from litellm.types.completion import ChatCompletionSystemMessageParam

                cls._litellm_types_cache[type_name] = ChatCompletionSystemMessageParam
            elif type_name == "ChatCompletionUserMessageParam":
                from litellm.types.completion import ChatCompletionUserMessageParam

                cls._litellm_types_cache[type_name] = ChatCompletionUserMessageParam
            elif type_name == "ChatCompletionAssistantMessageParam":
                from litellm.types.completion import ChatCompletionAssistantMessageParam

                cls._litellm_types_cache[type_name] = (
                    ChatCompletionAssistantMessageParam
                )
            elif type_name == "ChatCompletionToolMessageParam":
                from litellm.types.completion import ChatCompletionToolMessageParam

                cls._litellm_types_cache[type_name] = ChatCompletionToolMessageParam
            elif type_name == "Function":
                from litellm.types.completion import Function

                cls._litellm_types_cache[type_name] = Function
            elif type_name == "ChatCompletionMessageToolCallParam":
                from litellm.types.completion import ChatCompletionMessageToolCallParam

                cls._litellm_types_cache[type_name] = ChatCompletionMessageToolCallParam
            else:
                raise ValueError(f"Unknown litellm type: {type_name}")
        return cls._litellm_types_cache[type_name]

    def __init__(
        self,
        **kwargs: Unpack[ModelConfig],
    ):
        super().__init__()  # Don't pass kwargs to EventRouter
        self._override_config = kwargs
        self._debug = kwargs.get("debug", False)

        # Create ManagedRouter with isolated callbacks
        self._litellm = None
        self._router: "ManagedRouter | None" = None
        self._instructor_patched = False
        self._instructor = None  # Will hold the instructor-patched router

        # Usage tracking
        self.total_tokens = 0
        self.total_cost = 0.0
        self.last_usage: Any = None
        self.last_cost: Any = None

        # Request/response tracking for debugging
        self.api_requests: list[Any] = []
        self.api_response_kwargs: list[dict[str, Any]] = []
        self.api_stream_responses: list[StreamChunk] = []
        self.api_responses: list[Any] = []
        self.api_errors: list[Any] = []

    def _clone_init_args(self):
        return (), copy.deepcopy(self._override_config)

    @property
    def config(self) -> AgentConfigManager:
        return self.agent.config

    @classmethod
    def register_model_override(cls, override):
        """Register a custom model override at runtime"""
        model_override_registry.register(override)

    @classmethod
    def get_model_overrides(cls, model_name: str) -> dict:
        """Get information about what overrides apply to a specific model"""
        return model_override_registry.get_model_info(model_name)

    async def async_log_pre_api_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> None:
        """Pre-API call logging hook"""
        # This is a placeholder for any pre-call logging logic
        # Currently, we don't need to do anything here
        self.api_requests.append({"model": model, "messages": messages, **kwargs})
        if self._debug:
            logger.debug(
                f"Pre-API call logging hook triggered - {model=}, {messages=}, {kwargs=}"
            )

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Success event logging hook"""
        self.api_responses.append(response_obj)
        self.api_response_kwargs.append(kwargs)
        self._update_usage(response_obj)
        # This is a placeholder for any success event logging logic
        # Currently, we don't need to do anything here
        if self._debug:
            logger.debug(
                f"Success event logging hook triggered - {kwargs=}, {response_obj=}, {start_time=}, {end_time=}"
            )

    async def async_log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Error event logging hook"""
        self.api_errors.append(response_obj)
        self.api_responses.append(response_obj)
        self.api_response_kwargs.append(kwargs)
        # This is a placeholder for any error event logging logic
        # Currently, we don't need to do anything here
        logger.debug(
            f"Error event logging hook triggered - {kwargs=}, {response_obj=}, {start_time=}, {end_time=}"
        )

    async def async_log_stream_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: float,
        end_time: float,
    ) -> None:
        """Stream event logging hook"""
        self.api_stream_responses.append(response_obj)
        self.api_response_kwargs.append(kwargs)
        self.agent.do("")

        logger.debug(
            f"Stream event logging hook triggered - {kwargs=}, {response_obj=}, {start_time=}, {end_time=}"
        )

    def supports_function_calling(self, model: str | None = None) -> bool:
        """Check if the model supports function calling"""
        model_name = model or self.model

        # Check our registry first (it has precedence for custom models)
        capabilities = model_override_registry.get_model_capabilities(model_name)

        # If we have a specific override, use it
        if any(
            override.matches(model_name)
            for override in model_override_registry._overrides
        ):
            return capabilities.function_calling

        # Otherwise try litellm
        try:
            return self.litellm.supports_function_calling(model_name)
        except (AttributeError, Exception):
            # Fall back to our capability value
            return capabilities.function_calling

    def supports_parallel_function_calling(self, model: str | None = None) -> bool:
        """Check if the model supports parallel function calling"""
        model_name = model or self.model

        # Check our registry first (it has precedence for custom models)
        capabilities = model_override_registry.get_model_capabilities(model_name)

        # If we have a specific override, use it
        if any(
            override.matches(model_name)
            for override in model_override_registry._overrides
        ):
            return capabilities.parallel_function_calling

        # Otherwise try litellm
        try:
            return self.litellm.supports_parallel_function_calling(model_name)
        except (AttributeError, Exception):
            # Fall back to our capability value
            return capabilities.parallel_function_calling

    def supports_images(self, model: str | None = None) -> bool:
        """Check if the model supports image inputs"""
        model_name = model or self.model

        # Check our registry first (it has precedence for custom models)
        capabilities = model_override_registry.get_model_capabilities(model_name)

        # If we have a specific override, use it
        if any(
            override.matches(model_name)
            for override in model_override_registry._overrides
        ):
            return capabilities.vision

        # Otherwise try litellm's vision support if available
        try:
            if hasattr(self.litellm, "supports_vision"):
                return self.litellm.supports_vision(model_name)
        except Exception:
            pass

        # Fall back to our capability value
        return capabilities.vision

    def supports_pdf_input(self, model: str | None = None) -> bool:
        """Check if the model supports PDF inputs"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.pdf_input

    def supports_citations(self, model: str | None = None) -> bool:
        """Check if the model supports citations"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.citations

    def supports_structured_output(self, model: str | None = None) -> bool:
        """Check if the model supports structured output (JSON mode, etc.)"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.response_schema

    def supports_streaming(self, model: str | None = None) -> bool:
        """Check if the model supports streaming responses"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.native_streaming

    def supports_audio(self, model: str | None = None) -> tuple[bool, bool]:
        """Check if the model supports audio input/output
        Returns: (supports_audio_input, supports_audio_output)
        """
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.audio_input, capabilities.audio_output

    def supports_video(self, model: str | None = None) -> bool:
        """Check if the model supports video inputs"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.video_input

    def supports_web_search(self, model: str | None = None) -> bool:
        """Check if the model supports web search"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.web_search

    def supports_context_caching(self, model: str | None = None) -> bool:
        """Check if the model supports context/prompt caching"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.prompt_caching

    def supports_reasoning(self, model: str | None = None) -> bool:
        """Check if the model supports advanced reasoning modes"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.reasoning

    def get_capabilities(self, model: str | None = None) -> dict[str, bool]:
        """Get all capabilities for a model as a dictionary"""
        model_name = model or self.model
        capabilities = model_override_registry.get_model_capabilities(model_name)
        return capabilities.to_dict()

    @overload
    def create_message(
        self,
        *content_parts: MessageContent,
        role: Literal["user"],
        output: Literal[None] = None,
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> UserMessage: ...

    @overload
    def create_message(
        self,
        *content_parts: MessageContent,
        role: Literal["assistant"],
        output: Literal[None] = None,
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> AssistantMessage: ...

    @overload
    def create_message(
        self,
        *content_parts: MessageContent,
        role: Literal["assistant"],
        output: BaseModel,
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> AssistantMessageStructuredOutput: ...

    @overload
    def create_message(
        self,
        *content_parts: MessageContent,
        role: Literal["system"],
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> SystemMessage: ...

    @overload
    def create_message(
        self,
        *content_parts: MessageContent,
        role: Literal["tool"],
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> ToolMessage: ...

    @overload
    def create_message(self, content: T_Message) -> T_Message: ...

    @overload
    def create_message(
        self,
        *content_parts: MessageContent,
        role: MessageRole = "user",
        output: BaseModel | None = None,
        context: dict[str, Any] | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> Message: ...

    def create_message(
        self,
        *content_parts: MessageContent | Message,
        role: MessageRole = "user",
        output: BaseModel | None = None,
        citations: list[URL | str] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a message based on role type"""

        if len(content_parts) == 0:
            if _content := kwargs.pop("content", None):
                # Convert to tuple for proper typing
                if not isinstance(_content, (list, tuple)):
                    content_parts = tuple([_content])
                else:
                    content_parts = (
                        tuple(_content) if isinstance(_content, list) else _content
                    )
                # logger.debug(_content)

        if len(content_parts) == 1 and isinstance(content_parts[0], Message):
            # If a single Message object is passed, set agent and return it directly
            message = content_parts[0]
            # do we need to re-render the content here?
            logger.debug("setting agent on existing message")
            message._set_agent(self.agent)
            return message
        parts: list[MessageContent] = []
        for item in content_parts:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    # Pass raw string for template detection
                    parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    # Handle multimodal responses - these need to be ContentPart objects
                    image_data = item.get("image_url", {})
                    parts.append(
                        ImageContentPart(
                            image_url=image_data.get("url"),
                            detail=image_data.get("detail", "auto"),
                        )
                    )
            elif isinstance(
                item,
                (
                    TextContentPart,
                    TemplateContentPart,
                    ImageContentPart,
                    FileContentPart,
                ),
            ):
                # Already a content part, pass through
                parts.append(item)
            else:
                # Pass raw content for template detection
                parts.append(item)

        # extract tool calls
        tool_calls = kwargs.pop("tool_calls", None)
        if tool_calls:
            # Convert ToolCall objects to dicts
            tool_calls_list = []
            for tc in tool_calls:
                tool_call_dict = {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                tool_calls_list.append(tool_call_dict)
            kwargs["tool_calls"] = tool_calls_list

        ctx = self.agent.apply_sync(
            AgentEvents.MESSAGE_CREATE_BEFORE,
            role=role,
            content=parts,
            response_output=output,
            citations=citations,
            extra_kwargs=kwargs,
        )

        parts = ctx.parameters.get("content", None) or parts
        kwargs = ctx.parameters.get("extra_kwargs", None) or kwargs
        output = ctx.parameters.get("response_output", None) or output
        citations = ctx.parameters.get("citations", None) or citations

        # Add citations to kwargs if provided
        if citations is not None:
            kwargs["citations"] = citations

        # Create message
        if role == "system":
            message = SystemMessage(
                *parts,
                **kwargs,
            )
        elif role == "user":
            message = UserMessage(
                *parts,
                **kwargs,
            )
        elif role == "assistant" and output is not None:
            # If output is provided, create an AssistantMessageStructuredOutput
            message = AssistantMessageStructuredOutput(
                *parts,
                output=output,
                **kwargs,
            )
        elif role == "assistant":
            # For assistant messages, we can pass additional kwargs
            message = AssistantMessage(
                *parts,
                **kwargs,
            )
        elif role == "tool":
            message = ToolMessage(
                *parts,
                **kwargs,
            )
        else:
            raise ValueError(f"Unknown role: {role}")

        # Set agent reference
        logger.debug(f"setting agent {self.agent} on existing message")
        message._set_agent(self.agent)

        self.agent.do(AgentEvents.MESSAGE_CREATE_AFTER, message=message)

        return message

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with override precedence"""
        return self._override_config.get(key, self.config.get(key, default))

    @property
    def model(self) -> str:
        """Get the model name"""
        return cast(str, self._get_config_value("model", DEFAULT_MODEL))

    @property
    def temperature(self) -> float:
        """Get the temperature setting"""
        return cast(float, self._get_config_value("temperature", DEFAULT_TEMPERATURE))

    @property
    def max_retries(self) -> int:
        """Get max retry attempts"""
        return cast(int, self._get_config_value("max_retries", 3))

    @property
    def fallback_models(self) -> list[str]:
        """Get fallback model list"""
        return cast(list[str], self._get_config_value("fallback_models", []))

    @property
    def router(self) -> "ManagedRouter":
        """Lazy-loaded ManagedRouter with isolated callbacks"""
        if not self._router:
            # Lazy import factory function only when needed
            from .manager import create_managed_router

            # Get model configuration
            model_name = self.model

            # Create model list for router
            # For now, use a simple single-model setup
            # In the future, this could include fallback models
            model_list = [
                {
                    "model_name": model_name,
                    "litellm_params": {
                        "model": model_name,
                    },
                }
            ]

            # Add fallback models if configured
            for fallback_model in self.fallback_models:
                model_list.append(
                    {
                        "model_name": fallback_model,
                        "litellm_params": {
                            "model": fallback_model,
                        },
                    }
                )

            # Create ManagedRouter (no callbacks needed - we track directly)

            self._router = create_managed_router(
                model_list=model_list,
                managed_callbacks=[
                    self
                ],  # LanguageModel implements CustomLogger callbacks
                routing_strategy="simple-shuffle",  # Could be configurable
                set_verbose=self._get_config_value("debug", False),
            )

            # logger.debug(f"Created ManagedRouter with {len(model_list)} models")

        return self._router

    @property
    def litellm(self) -> Any:
        """Compatibility property - returns router for gradual migration"""
        if not self._litellm:
            import litellm

            self._litellm = litellm
        return self._litellm

    @property
    def instructor(self) -> "ManagedRouter":
        """Lazy-loaded instructor instance"""
        if not self._instructor:
            # Get instructor mode from config
            instructor_mode = self._get_config_value("instructor_mode", None)

            # Patch our router with instructor
            self.router.patch_with_instructor(mode=instructor_mode)
            self._instructor_patched = True
            self._instructor = self.router  # Router now has extract/aextract methods
        return self._instructor

    def _prepare_request_config(self, **kwargs: Unpack[ModelConfig]) -> dict[str, Any]:
        """Prepare configuration for litellm request with model-specific overrides"""
        # TODO - why repeated calls?
        config = {}

        # Start with defaults
        config.update(
            {
                "model": self.model,
                "temperature": self.temperature,
            }
        )

        # Apply config manager values via shared pass-through keys
        for key in PASS_THROUGH_KEYS:
            value = self._get_config_value(key)
            if value is not None:
                config[key] = value

        # Apply method-level overrides
        for key, value in kwargs.items():
            if key not in FILTER_ARGS and value is not None:
                config[key] = value

        # Ensure we always have a sane timeout to prevent indefinite hangs if cancellation
        # does not propagate from the runner/environment. Prefer explicit config, otherwise
        # fall back to a reasonable default.
        if config.get("timeout") in (None, "", 0):
            # Use agent/global timeout if provided, else default to 30s
            default_timeout = self._get_config_value("timeout", 30.0)
            # Some backends expect a float seconds value
            try:
                # Coerce httpx.Timeout to total seconds if provided
                from httpx import Timeout as _HTTPXTimeout  # local import

                if isinstance(default_timeout, _HTTPXTimeout):
                    # httpx.Timeout exposes attributes; prefer total or fallback to 30.0
                    total = getattr(default_timeout, "_timeout", None)
                    config["timeout"] = float(total) if total else 30.0
                else:
                    config["timeout"] = (
                        float(default_timeout) if default_timeout else 30.0
                    )
            except Exception:
                config["timeout"] = 30.0

        # Apply model-specific overrides LAST so they take precedence
        model_name = str(config.get("model", self.model))
        config = model_override_registry.apply(model_name, config)

        # Provider hints: auto-set openrouter provider when detectable
        base_url = config.get("base_url") or self._get_config_value("base_url")
        if "custom_llm_provider" not in config and (
            (isinstance(model_name, str) and model_name.startswith("openrouter/"))
            or (isinstance(base_url, str) and "openrouter.ai" in base_url)
        ):
            config["custom_llm_provider"] = "openrouter"

        # OpenRouter sensible defaults and param normalization
        if config.get("custom_llm_provider") == "openrouter":
            # Default transforms to middle-out if not provided
            if "transforms" not in config:
                config["transforms"] = ["middle-out"]

            # If model supports reasoning, default to include_reasoning=True
            caps = model_override_registry.get_model_capabilities(model_name)
            if caps.reasoning and "include_reasoning" not in config:
                config["include_reasoning"] = True

            # Normalize OpenRouter-specific identifiers in extra params
            def _strip_or_prefix(val: Any) -> Any:
                if isinstance(val, str) and val.startswith("openrouter/"):
                    return val.split("/", 1)[1]
                return val

            # Normalize 'models' parameter (list/str/dict shapes)
            if "models" in config:
                models_val = config.get("models")
                if isinstance(models_val, list):
                    config["models"] = [_strip_or_prefix(m) for m in models_val]
                elif isinstance(models_val, str):
                    config["models"] = _strip_or_prefix(models_val)
                elif isinstance(models_val, dict):
                    normalized = {}
                    for k, v in models_val.items():
                        if isinstance(v, list):
                            normalized[k] = [_strip_or_prefix(m) for m in v]
                        else:
                            normalized[k] = _strip_or_prefix(v)
                    config["models"] = normalized

            # Normalize 'route' if user passed a prefixed id
            if "route" in config and isinstance(config.get("route"), str):
                config["route"] = _strip_or_prefix(config["route"])

        # Ensure parallel_tool_calls is only sent when tools are specified
        if "parallel_tool_calls" in config and not config.get("tools"):
            # Some providers reject this flag without accompanying tools
            config.pop("parallel_tool_calls", None)

        # Log if any overrides were applied (for debugging)
        model_override_registry.get_model_info(model_name)

        return config

    def _update_usage(self, response: "ModelResponse") -> None:
        """Update usage tracking from response"""
        # Type-safe approach: getattr with explicit type annotation
        # This satisfies both runtime safety and type checkers
        usage: Usage | None = getattr(response, "usage", None)
        if usage is None:
            # logger.debug(f"Response has no usage attribute: {type(response)}")
            return

        # Type guard - we know usage exists and is not None
        # Check if usage has meaningful data (not just defaults)
        if usage.total_tokens > 0:
            self.last_usage = usage
            self.total_tokens += usage.total_tokens
            # logger.debug(
            #     f"Updated total_tokens to {self.total_tokens} from usage: {usage}"
            # )
        else:
            # Usage exists but has no tokens (might be default)
            # logger.debug(f"Usage object has zero tokens: {usage}")
            pass

        # Calculate cost if available
        try:
            # Use litellm's completion_cost function directly
            cost = self.litellm.completion_cost(response)
            if cost:
                self.last_cost = cost
                self.total_cost += cost
        except Exception:
            # logger.debug(f"Could not calculate cost: {e}")
            pass

    async def _format_message_content(
        self,
        content_parts: list[ContentPartType],
        message: Message,
        mode: RenderMode = RenderMode.LLM,
    ):
        # Multiple or complex parts return list

        ctx = await self.agent.apply(
            AgentEvents.MESSAGE_RENDER_BEFORE,
            output=content_parts,
            message=message,
            mode=mode,
        )

        content_parts = ctx.output or content_parts

        result = []
        for part in content_parts:
            if isinstance(part, TextContentPart):
                ChatCompletionContentPartTextParam = self._get_litellm_type(
                    "ChatCompletionContentPartTextParam"
                )
                result.append(
                    ChatCompletionContentPartTextParam(text=part.text, type="text")
                )
            elif isinstance(part, TemplateContentPart):
                # Render template for LLM
                rendered = message._render_part(part, mode)
                ChatCompletionContentPartTextParam = self._get_litellm_type(
                    "ChatCompletionContentPartTextParam"
                )
                result.append(
                    ChatCompletionContentPartTextParam(text=rendered, type="text")
                )
            elif isinstance(part, ImageContentPart):
                if part.image_url:
                    ChatCompletionContentPartImageParam = self._get_litellm_type(
                        "ChatCompletionContentPartImageParam"
                    )
                    ImageURL = self._get_litellm_type("ImageURL")
                    result.append(
                        ChatCompletionContentPartImageParam(
                            image_url=ImageURL(url=str(part.image_url)),
                            type="image_url",
                        )
                    )
                elif part.image_base64:
                    ChatCompletionContentPartImageParam = self._get_litellm_type(
                        "ChatCompletionContentPartImageParam"
                    )
                    ImageURL = self._get_litellm_type("ImageURL")
                    result.append(
                        ChatCompletionContentPartImageParam(
                            image_url=ImageURL(
                                url=part.image_base64, detail=part.detail
                            ),
                            type="image_url",
                        )
                    )
            elif isinstance(part, FileContentPart):
                if part.file_path:
                    ChatCompletionFileObject = self._get_litellm_type(
                        "ChatCompletionFileObject"
                    )
                    ChatCompletionFileObjectFile = self._get_litellm_type(
                        "ChatCompletionFileObjectFile"
                    )
                    result.append(
                        ChatCompletionFileObject(
                            file=ChatCompletionFileObjectFile(file_id=part.file_path),
                            type="file",
                        )
                    )

        ctx = await self.agent.apply(
            AgentEvents.MESSAGE_RENDER_AFTER,
            output=result,
            message=message,
            mode=mode,
        )

        return ctx.output or result

    async def _format_message(
        self,
        message: Message,
        mode: RenderMode = RenderMode.LLM,
    ) -> "ChatCompletionMessageParam":
        match message:
            case SystemMessage():
                # Render content for LLM mode
                _content = await self._format_message_content(
                    message.content_parts, message=message, mode=mode
                )
                ChatCompletionSystemMessageParam = self._get_litellm_type(
                    "ChatCompletionSystemMessageParam"
                )
                return ChatCompletionSystemMessageParam(
                    content=_content
                    if isinstance(_content, str)
                    else "".join(
                        part.get("text", "")
                        for part in _content
                        if isinstance(part, dict) and part.get("type") == "text"
                    ),
                    role="system",
                )

            case UserMessage(images=images, image_detail=image_detail):
                # Format content parts with events
                _content = await self._format_message_content(
                    message.content_parts, message=message, mode=mode
                )

                # Add legacy images if present
                if images:
                    if not isinstance(_content, list):
                        _content = [_content] if _content else []

                    for image in images:
                        if isinstance(image, URL):
                            ChatCompletionContentPartImageParam = (
                                self._get_litellm_type(
                                    "ChatCompletionContentPartImageParam"
                                )
                            )
                            ImageURL = self._get_litellm_type("ImageURL")
                            _content.append(
                                ChatCompletionContentPartImageParam(
                                    image_url=ImageURL(url=str(image)),
                                    type="image_url",
                                )
                            )
                        elif isinstance(image, bytes):
                            ChatCompletionContentPartImageParam = (
                                self._get_litellm_type(
                                    "ChatCompletionContentPartImageParam"
                                )
                            )
                            ImageURL = self._get_litellm_type("ImageURL")
                            _content.append(
                                ChatCompletionContentPartImageParam(
                                    image_url=ImageURL(
                                        url=url_to_base64(image), detail=image_detail
                                    ),
                                    type="image_url",
                                )
                            )

                # Return the formatted user message
                ChatCompletionUserMessageParam = self._get_litellm_type(
                    "ChatCompletionUserMessageParam"
                )
                if isinstance(_content, str):
                    return ChatCompletionUserMessageParam(
                        content=_content,
                        role="user",
                    )
                else:
                    return ChatCompletionUserMessageParam(
                        content=_content,
                        role="user",
                    )
            case AssistantMessage(tool_calls=tool_calls):
                # Format content parts with events
                _content = await self._format_message_content(
                    message.content_parts, message=message, mode=mode
                )

                # Convert content to string if it's a list
                if isinstance(_content, list):
                    # Join text parts for assistant messages
                    _content = (
                        "".join(
                            part.get("text", "")
                            if isinstance(part, dict)
                            else str(part)
                            for part in _content
                            if isinstance(part, dict) and part.get("type") == "text"
                        )
                        or ""
                    )

                # Build the assistant message
                ChatCompletionAssistantMessageParam = self._get_litellm_type(
                    "ChatCompletionAssistantMessageParam"
                )
                assistant_msg = ChatCompletionAssistantMessageParam(
                    role="assistant",
                    content=_content,
                )

                # Add tool calls if present
                if tool_calls:
                    # Convert our ToolCall objects to litellm format
                    ChatCompletionMessageToolCallParam = self._get_litellm_type(
                        "ChatCompletionMessageToolCallParam"
                    )
                    Function = self._get_litellm_type("Function")
                    tool_calls_list: list[Any] = []  # Use Any for runtime dynamic types
                    for tc in tool_calls:
                        tool_call_dict = ChatCompletionMessageToolCallParam(
                            id=tc.id,
                            type=tc.type,
                            function=Function(
                                name=tc.function.name,
                                arguments=tc.function.arguments,
                            ),
                        )
                        tool_calls_list.append(tool_call_dict)
                    assistant_msg["tool_calls"] = tool_calls_list

                return assistant_msg

            case ToolMessage(tool_call_id=tool_call_id):
                # Format content parts with events
                _content = await self._format_message_content(
                    message.content_parts, message=message, mode=mode
                )

                # Convert content to string if it's a list
                if isinstance(_content, list):
                    # Join text parts for tool messages
                    _content = (
                        "".join(
                            part.get("text", "")
                            if isinstance(part, dict)
                            else str(part)
                            for part in _content
                            if isinstance(part, dict) and part.get("type") == "text"
                        )
                        or ""
                    )

                ChatCompletionToolMessageParam = self._get_litellm_type(
                    "ChatCompletionToolMessageParam"
                )
                return ChatCompletionToolMessageParam(
                    role="tool",
                    content=_content,
                    tool_call_id=tool_call_id,
                )

            case _:
                # Fallback for any other message type
                raise ValueError(f"Unsupported message type: {type(message)}")

    async def format_message_list_for_llm(
        self, messages: list[Message]
    ) -> list["ChatCompletionMessageParam | dict[str, Any]"]:
        """Format a list of messages for LLM consumption with event hooks.

        This method handles all message formatting including:
        - Firing render events for extensions
        - Converting content parts to LLM format
        - Handling templates, images, and files
        - Ensuring tool call/response pairs are valid (injects synthetic tool responses)

        Args:
            messages: List of Message objects to format

        Returns:
            List of formatted messages ready for LLM API, with synthetic tool
            responses injected for any assistant messages with tool_calls that
            don't have corresponding tool responses
        """
        # Process messages in order (not parallel) to maintain sequence
        messages_for_llm = []
        for msg in messages:
            formatted = await self._format_message(msg, RenderMode.LLM)
            messages_for_llm.append(formatted)

        # Ensure all tool calls have corresponding tool responses
        # This is critical for AssistantMessageStructuredOutput which may have
        # tool_calls in the message history but no actual ToolMessage responses
        messages_for_llm = self._ensure_tool_call_pairs_for_formatted_messages(
            messages_for_llm
        )

        return messages_for_llm

    def _ensure_tool_call_pairs_for_formatted_messages(
        self, messages: Sequence["ChatCompletionMessageParam | dict[str, Any]"]
    ) -> list["ChatCompletionMessageParam"]:
        """Ensure assistant messages with tool_calls are immediately followed by
        corresponding tool messages in the payload sent to the API.

        This does NOT modify agent history; it only adjusts the outbound message list.
        """

        # Helper to access attributes on dict-like or object-like instances
        def _get_attr(obj: Any, key: str, default: Any = None) -> Any:
            try:
                if hasattr(obj, "get"):
                    return obj.get(key, default)  # type: ignore[attr-defined]
            except Exception:
                pass
            try:
                return getattr(obj, key)
            except Exception:
                return default

        ChatCompletionToolMessageParam = self._get_litellm_type(
            "ChatCompletionToolMessageParam"
        )

        result: list["ChatCompletionMessageParam"] = []
        i = 0
        n = len(messages)
        while i < n:
            msg = messages[i]
            role = _get_attr(msg, "role", None)

            # If assistant with tool_calls, ensure immediate tool responses exist
            tool_calls = (
                _get_attr(msg, "tool_calls", None) if role == "assistant" else None
            )
            if role == "assistant" and tool_calls:
                # Append the assistant message first
                result.append(msg)

                # Collect IDs from assistant's tool calls
                assistant_call_ids: list[str] = []
                try:
                    for tc in tool_calls:
                        # tc may be dict-like or object-like
                        tc_id = _get_attr(tc, "id", None)
                        if tc_id:
                            assistant_call_ids.append(tc_id)
                except Exception:
                    assistant_call_ids = []

                # Append any immediate tool messages that follow in the source list
                existing_ids: set[str] = set()
                j = i + 1
                while j < n and _get_attr(messages[j], "role", None) == "tool":
                    tm = messages[j]
                    result.append(tm)
                    tcid = _get_attr(tm, "tool_call_id", None)
                    if isinstance(tcid, str):
                        existing_ids.add(tcid)
                    j += 1

                # Inject synthetic tool messages for any missing tool_call IDs
                for tc_id in assistant_call_ids:
                    if tc_id not in existing_ids:
                        result.append(
                            ChatCompletionToolMessageParam(
                                role="tool", content="{}", tool_call_id=tc_id
                            )
                        )

                # Advance pointer past the immediate tool message block
                i = j
                continue

            # Default path: pass-through
            result.append(msg)
            i += 1

        return result

    @overload
    async def complete(
        self,
        messages: Sequence["ChatCompletionMessageParam | dict[str, Any]"],
        *,
        stream: Literal[False] = False,
        **kwargs: Unpack[ModelConfig],
    ) -> "ModelResponse": ...

    @overload
    async def complete(
        self,
        messages: Sequence["ChatCompletionMessageParam | dict[str, Any]"],
        *,
        stream: Literal[True] = True,
        **kwargs: Unpack[ModelConfig],
    ) -> "ModelResponse": ...

    async def complete(
        self,
        messages: Sequence["ChatCompletionMessageParam | dict[str, Any]"],
        stream: bool = False,
        **kwargs: Unpack[ModelConfig],
    ) -> "ModelResponse":
        """PURPOSE: Execute LLM chat completion with retry logic and fallback model support.

        PURPOSE: Core method for LLM interactions that handles:
        - Message formatting and validation for LLM API compatibility
        - Model-specific parameter application and validation
        - Automatic retry with exponential backoff on failures
        - Fallback model routing when primary model fails
        - Usage tracking and cost calculation
        - Event emission for monitoring and debugging

        WHEN TO USE:
        - Primary method for standard chat completions
        - When you need full response objects with metadata
        - For scenarios requiring retry/fallback logic
        - When token usage tracking is important
        - Use stream() for real-time response streaming
        - Use extract() for structured output extraction

        EXECUTION FLOW:
        1. Configuration Preparation: Apply model overrides and parameter validation
        2. Event Emission: LLM_COMPLETE_BEFORE with messages and config
        3. Router Execution: ManagedRouter handles retry/fallback logic
        4. Usage Tracking: Update token counts and cost calculation
        5. Event Emission: LLM_COMPLETE_AFTER with response metadata
        6. Error Handling: LLM_COMPLETE_ERROR event on failures

        FALLBACK STRATEGY:
        - Primary model attempted first with configured retry count
        - Sequential fallback to models in fallback_models list
        - Model-specific parameter overrides applied for each attempt
        - Final response from first successful model completion
        - All attempts logged for debugging and monitoring

        SIDE EFFECTS:
        - Updates usage statistics: total_tokens, total_cost, last_usage
        - Emits lifecycle events for monitoring and debugging
        - Tracks API requests/responses in instance history
        - May trigger model override application and validation
        - Updates ManagedRouter routing statistics

        ERROR HANDLING:
        - Network failures: Automatic retry with exponential backoff
        - Model unavailability: Automatic fallback to alternative models
        - Parameter validation: Model overrides filter unsupported parameters
        - Authentication errors: Propagated after all fallback attempts exhausted
        - Rate limiting: Handled by router with retry delays

        CONCURRENCY:
        - Method is NOT thread-safe - one completion per LanguageModel instance
        - Multiple LanguageModel instances can operate concurrently
        - ManagedRouter provides connection pooling and isolation
        - Event emission is non-blocking for completion performance

        PERFORMANCE:
        - Latency: Primary model + fallback attempts if needed (typically 500ms-3s)
        - Throughput: Limited by slowest model in fallback chain
        - Memory: Efficient message formatting and response handling
        - Network: Connection pooling via ManagedRouter reduces overhead

        Args:
            messages: Sequence of chat completion messages in litellm format.
                Can include system, user, assistant, and tool messages.
                Messages should be properly formatted for the target model.
            stream: Whether to stream the response (default: False).
                When True, returns streaming response iterator.
                Use stream() method for more convenient streaming interface.
            **kwargs: Additional model configuration parameters.
                Supports all ModelConfig options including temperature,
                max_tokens, tools, etc. Model-specific overrides applied automatically.

        Returns:
            ModelResponse: Complete LLM response with full metadata including:
            - choices: Response content and finish reason
            - usage: Token consumption statistics
            - model: Model name that generated the response
            - created: Response timestamp
            - Additional provider-specific metadata

        Raises:
            Exception: When all models (primary + fallbacks) fail.
                Original exception from last failed attempt included.
            ValidationError: When message format is invalid for target model.
            ConfigurationError: When model configuration is invalid or incomplete.

        TYPICAL USAGE:
        ```python
        # Basic completion
        messages = [{"role": "user", "content": "Hello, how are you?"}]
        response = await llm.complete(messages)
        print(response.choices[0].message.content)

        # With temperature and max_tokens
        response = await llm.complete(messages, temperature=0.7, max_tokens=1000)

        # With tool calling
        response = await llm.complete(messages, tools=[tool_schema], tool_choice="auto")

        # Error handling with fallback
        try:
            response = await llm.complete(messages)
        except Exception as e:
            logger.error(f"All models failed: {e}")
            # Handle complete failure scenario
        ```

        MONITORING:
        - Track usage via llm.total_tokens and llm.total_cost
        - Monitor events LLM_COMPLETE_BEFORE/AFTER for timing
        - Check api_requests and api_responses for debugging
        - Use debug=True for detailed execution logging
        - Monitor fallback model usage via router statistics

        RELATED:
        - extract(): Structured output extraction
        - stream(): Real-time response streaming
        - create_message(): Message creation and formatting
        - _prepare_request_config(): Configuration preparation
        - router.acompletion(): Low-level router interaction
        """
        import time

        # Note: messages already have tool call pairs ensured by format_message_list_for_llm()

        kwargs["stream"] = stream  # type: ignore Ensure stream is always set in kwargs

        config = self._prepare_request_config(**kwargs)

        # Apply model-specific overrides LAST so they take precedence
        model_name = str(config.get("model", self.model))
        config = model_override_registry.apply(model_name, config)

        # Fire before event (using apply_typed for type safety)
        start_time = time.time()
        ctx = await self.agent.apply_typed(
            AgentEvents.LLM_COMPLETE_BEFORE,
            CompletionEvent,
            None,  # No specific return type expected for 'before' event
            messages=messages,
            config=config,
            llm=self,
        )

        if "parallel_tool_calls" in ctx.parameters["config"] and not ctx.parameters[
            "config"
        ].get("tools"):
            logger.warning("`parallel_tool_calls` added back in")

        # # Ensure parallel_tool_calls is still not present after event handlers
        # # Event handlers might have modified ctx.parameters["config"]
        # if "parallel_tool_calls" in ctx.parameters["config"] and not ctx.parameters[
        #     "config"
        # ].get("tools"):
        #     ctx.parameters["config"].pop("parallel_tool_calls", None)

        try:
            # Router already handles retries/fallbacks via model_list configuration
            response = await self.router.acompletion(
                messages=ctx.parameters["messages"],
                **ctx.parameters["config"],
            )
            # Usage is updated in async_log_success_event callback

            # Fire after event
            end_time = time.time()

            from litellm.types.utils import ModelResponse

            # Lazy load ModelResponse for type parameter
            # Always use apply_typed at runtime

            ctx = await self.agent.apply_typed(
                AgentEvents.LLM_COMPLETE_AFTER,
                CompletionEvent,
                ModelResponse,
                output=response,
                config=config,
                llm=self,
            )
            assert ctx.output is not None, "After event must return output"
            return ctx.output
        except (asyncio.CancelledError, KeyboardInterrupt):
            # Propagate cancellations immediately without additional handling
            raise
        except Exception as e:
            # Fire error event
            end_time = time.time()
            self.do(
                AgentEvents.LLM_COMPLETE_ERROR,
                error=e,
                parameters=config,
                start_time=start_time,
                end_time=end_time,
                language_model=self,
            )
            raise

    async def extract(
        self,
        messages: Sequence["ChatCompletionMessageParam"],
        response_model: type[BaseModel],
        **kwargs: Unpack[ModelConfig],
    ) -> BaseModel:
        """PURPOSE: Extract structured data from LLM responses using instructor library.

        PURPOSE: Convert unstructured LLM responses into validated Pydantic models
        with automatic retry logic, fallback model support, and comprehensive error handling.

        WHEN TO USE:
        - When you need structured, typed responses from the LLM
        - For data extraction, classification, or entity recognition
        - When response validation and schema enforcement are required
        - For complex data structures that need type safety
        - Use complete() for free-form text responses

        EXECUTION FLOW:
        1. Model Validation: Check if target model supports structured output
        2. Configuration Prep: Apply model overrides and instructor settings
        3. Event Emission: LLM_EXTRACT_BEFORE with messages and schema
        4. Instructor Execution: aextract() with validation and retry logic
        5. Response Validation: Ensure BaseModel instance is returned
        6. Event Emission: LLM_EXTRACT_AFTER with validated response
        7. Error Handling: LLM_EXTRACT_ERROR on validation failures

        STRUCTURED OUTPUT PROCESS:
        - instructor patches the LLM with response model validation
        - LLM generates JSON response matching the Pydantic schema
        - instructor validates and converts response to BaseModel instance
        - Invalid responses trigger automatic retry with corrected prompts
        - Final response guaranteed to conform to the specified schema

        SIDE EFFECTS:
        - Patches router with instructor for structured output extraction
        - Emits extraction lifecycle events for monitoring
        - Updates usage tracking for token consumption
        - May trigger multiple LLM calls for validation retries
        - Stores extraction attempts in debugging history

        ERROR HANDLING:
        - Schema validation failures: Automatic retry with refined prompts
        - Model capability errors: Fallback to models with structured output support
        - JSON parsing errors: Retry with corrected extraction instructions
        - Timeout errors: Automatic retry with extended time limits
        - Complete failures: Detailed error messages with debugging context

        Args:
            messages: Sequence of chat messages for extraction context.
                Should include clear instructions about the data to extract.
                System messages should specify the extraction task.
            response_model: Pydantic BaseModel class for response validation.
                Defines the expected structure and validation rules.
                Must be a valid Pydantic model with proper type hints.
            **kwargs: Additional model configuration parameters.
                instructor_mode controls extraction strategy (TOOL, JSON, etc.)

        Returns:
            BaseModel: Validated instance of the response_model.
                Guaranteed to conform to the specified schema.
                Includes all validation rules and type constraints.
                Ready for immediate use in application logic.

        Raises:
            ValueError: If instructor returns None instead of BaseModel.
            ValidationError: If response cannot be validated against schema.
            Exception: When all extraction attempts fail across models.

        TYPICAL USAGE:
        ```python
        from pydantic import BaseModel


        class UserInfo(BaseModel):
            name: str
            age: int
            email: str


        messages = [
            {"role": "system", "content": "Extract user information from the text"},
            {
                "role": "user",
                "content": "John is 25 years old and emails john@example.com",
            },
        ]

        user_info = await llm.extract(messages, UserInfo)
        print(f"Name: {user_info.name}, Age: {user_info.age}")
        ```

        PERFORMANCE:
        - Latency: Higher than complete() due to validation overhead
        - Retry Logic: May require multiple LLM calls for complex schemas
        - Memory: Efficient validation without large intermediate structures
        - Cost: Potentially higher due to retry attempts

        RELATED:
        - complete(): Standard chat completion without structured output
        - create_message(): Message creation for extraction context
        - supports_structured_output(): Check model capability
        - instructor: Underlying structured output library
        """
        import time

        # Note: messages already have tool call pairs ensured by format_message_list_for_llm()

        config = self._prepare_request_config(**kwargs)

        # Apply model-specific overrides LAST so they take precedence
        model_name = str(config.get("model", self.model))
        config = model_override_registry.apply(model_name, config)

        # Fire before event (using apply_typed for type safety)
        start_time = time.time()
        ctx = await self.agent.apply_typed(
            AgentEvents.LLM_EXTRACT_BEFORE,
            CompletionEvent,
            None,  # No specific return type expected for 'before' event
            messages=messages,
            config=config,
            response_model=response_model,
            llm=self,
        )

        try:
            # Router already handles retries/fallbacks via model_list configuration
            response = await self.instructor.aextract(
                messages=list(ctx.parameters["messages"]),  # Use modified messages
                response_model=response_model,
                **ctx.parameters["config"],  # Use modified config
            )

            # Ensure response is not None (instructor should always return a BaseModel)
            if response is None:
                raise ValueError("Instructor returned None instead of BaseModel")

            # Fire after event
            end_time = time.time()
            self.do(
                AgentEvents.LLM_EXTRACT_AFTER,
                response=response,
                response_model=response_model,
                parameters=config,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                language_model=self,
            )

            return response

        except (asyncio.CancelledError, KeyboardInterrupt):
            # Propagate cancellations immediately
            raise
        except Exception as e:
            # Fire error event
            end_time = time.time()
            self.do(
                AgentEvents.LLM_EXTRACT_ERROR,
                error=e,
                response_model=response_model,
                parameters=config,
                start_time=start_time,
                end_time=end_time,
                duration=end_time - start_time,
                language_model=self,
            )
            raise

    async def stream(
        self,
        messages: Sequence["ChatCompletionMessageParam"],
        **kwargs: Unpack[ModelConfig],
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion response token by token.

        This method enables real-time streaming of LLM responses, yielding
        chunks as they arrive from the API. Each chunk contains partial
        content and optional finish reason.

        Args:
            messages: Sequence of chat messages
            **kwargs: Additional model configuration options

        Yields:
            StreamChunk: Individual response chunks with content and metadata

        Example:
            async for chunk in language_model.stream(messages):
                if chunk.content:
                    print(chunk.content, end='', flush=True)
        """
        import time

        # Force streaming in config
        kwargs["stream"] = True  # type: ignore
        config = self._prepare_request_config(**kwargs)
        model = config.get("model", self.model)

        # Ensure parallel_tool_calls is only sent when tools are specified
        if "parallel_tool_calls" in config and not config.get("tools"):
            # Some providers reject this flag without accompanying tools
            config.pop("parallel_tool_calls", None)

        # Fire before event
        start_time = time.time()
        self.do(
            AgentEvents.LLM_STREAM_BEFORE,
            model=model,
            messages=messages,
            parameters=config,
            language_model=self,
        )

        # Streaming with retry support
        models_to_try = [self.model] + self.fallback_models
        last_exception = None

        for attempt, model in enumerate(models_to_try):
            try:
                # Update config with current model
                config["model"] = model

                # Ensure parallel_tool_calls is still not present after event handlers
                if "parallel_tool_calls" in config and not config.get("tools"):
                    config.pop("parallel_tool_calls", None)

                # Use the router's streaming completion
                stream_response = await self.router.acompletion(
                    messages=list(messages), **config
                )

                # Ensure we have a valid streaming response
                if not hasattr(stream_response, "__aiter__"):
                    raise RuntimeError(
                        f"Router returned non-iterable response: {type(stream_response)}"
                    )

                # Track chunks for rebuilding complete response
                chunks = []

                # Yield chunks as they arrive
                # Cast to AsyncIterator to satisfy type checker after our runtime check
                from collections.abc import AsyncIterator

                stream_iter: AsyncIterator = stream_response
                async for chunk in stream_iter:
                    chunks.append(chunk)

                    # Extract content and finish reason from chunk
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        content = (
                            delta.get("content")
                            if hasattr(delta, "get")
                            else getattr(delta, "content", None)
                        )
                        finish_reason = (
                            chunk.choices[0].finish_reason
                            if hasattr(chunk.choices[0], "finish_reason")
                            else None
                        )

                        # Create and yield StreamChunk
                        stream_chunk = StreamChunk(
                            content=content, finish_reason=finish_reason
                        )

                        # Track for debugging
                        self.api_stream_responses.append(stream_chunk)

                        yield stream_chunk

                # Build complete response from chunks for tracking
                if chunks:
                    try:
                        # Use litellm's chunk builder to reconstruct the full response
                        complete_response = self.litellm.stream_chunk_builder(chunks)

                        # Update usage tracking
                        self._update_usage(complete_response)
                        self.api_responses.append(complete_response)

                        # Fire after event with complete response
                        end_time = time.time()
                        self.do(
                            AgentEvents.LLM_STREAM_AFTER,
                            response=complete_response,
                            chunks=chunks,
                            parameters=config,
                            start_time=start_time,
                            end_time=end_time,
                            language_model=self,
                        )
                    except Exception as e:
                        logger.debug(
                            f"Could not build complete response from chunks: {e}"
                        )

                # If we made it here, streaming succeeded
                if attempt > 0:
                    logger.info(f"Successfully used fallback model: {model}")

                return  # Exit the retry loop on success

            except (asyncio.CancelledError, KeyboardInterrupt):
                # Immediate cancellation for streaming; propagate upwards
                raise
            except Exception as e:
                last_exception = e
                logger.warning(f"Model {model} failed during streaming: {e}")

                if attempt < len(models_to_try) - 1:
                    logger.info("Trying fallback model...")
                    continue
                else:
                    logger.error(f"All models failed during streaming. Last error: {e}")
                    break

        # If we exhausted all models, fire error event and raise
        end_time = time.time()
        self.api_errors.append(last_exception)
        self.do(
            AgentEvents.LLM_STREAM_ERROR,
            error=last_exception,
            parameters=config,
            start_time=start_time,
            end_time=end_time,
            language_model=self,
        )

        if last_exception:
            raise last_exception
        else:
            raise Exception("All model attempts failed during streaming")
