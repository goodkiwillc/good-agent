"""Core LLM abstraction with multi-provider routing and structured output support."""

from __future__ import annotations

import asyncio
import copy
import logging
import time
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypeVar,
    Unpack,
    cast,
    overload,
)

from pydantic import BaseModel

from good_agent.agent.config import PASS_THROUGH_KEYS, AgentConfigManager, ModelConfig
from good_agent.core.components import AgentComponent
from good_agent.core.types import URL
from good_agent.events import AgentEvents
from good_agent.messages import (
    AssistantMessage,
    AssistantMessageStructuredOutput,
    Message,
    MessageContent,
    MessageRole,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from good_agent.model.capabilities import ModelCapabilities
from good_agent.model.formatting import MessageFormatter
from good_agent.model.manager import ManagedRouter, ModelManager
from good_agent.model.overrides import model_override_registry
from good_agent.model.protocols import (
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    FILTER_ARGS,
    CompletionEvent,
    StreamChunk,
)
from good_agent.model.streaming import StreamingHandler
from good_agent.model.structured import StructuredOutputExtractor

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from litellm.types.completion import ChatCompletionMessageParam
    from litellm.types.utils import ModelResponse, Usage

CACHE_DIR = Path("~/.good-intel/cache").expanduser()

T_Message = TypeVar("T_Message", bound=Message)


class LanguageModel(AgentComponent):
    """Core LLM abstraction providing unified interface for multi-provider language models.

    Orchestrates LLM interactions with comprehensive support for:
    - Multi-provider routing via litellm abstraction layer
    - Structured output extraction via instructor integration
    - Automatic retry and fallback model management
    - Model capability detection and parameter validation
    - Message formatting and content transformation
    - Token usage tracking and cost calculation

    Thread Safety: NOT thread-safe. Each LanguageModel instance should be used by
    only one async task at a time.

    Example:
        >>> llm = LanguageModel(model="gpt-4", temperature=0.7)
        >>> response = await llm.complete(messages)
        >>> structured = await llm.extract(messages, response_model=MySchema)
        >>> async for chunk in llm.stream(messages):
        ...     print(chunk.content, end="")
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

                cls._litellm_types_cache[type_name] = ChatCompletionContentPartImageParam
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

                cls._litellm_types_cache[type_name] = ChatCompletionAssistantMessageParam
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
        self._router: ManagedRouter | None = None
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

        # Helper modules - initialized after agent is set
        self._capabilities: ModelCapabilities | None = None
        self._formatter: MessageFormatter | None = None
        self._extractor: StructuredOutputExtractor | None = None
        self._streaming: StreamingHandler | None = None

    def _ensure_helpers(self):
        """Lazy initialization of helper modules (requires agent to be set)."""
        if self._capabilities is None:
            self._capabilities = ModelCapabilities(self)
            self._formatter = MessageFormatter(self)
            self._extractor = StructuredOutputExtractor(self)
            self._streaming = StreamingHandler(self)

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

    # ==================== Callback hooks ====================

    async def async_log_pre_api_call(
        self,
        model: str,
        messages: list[dict[str, Any]],
        kwargs: dict[str, Any],
    ) -> None:
        """Pre-API call logging hook"""
        self.api_requests.append({"model": model, "messages": messages, **kwargs})
        if self._debug:
            logger.debug(f"Pre-API call logging hook triggered - {model=}, {messages=}, {kwargs=}")

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

    # ==================== Capability delegation ====================

    def supports_function_calling(self, model: str | None = None) -> bool:
        """Check if the model supports function calling"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_function_calling(model)

    def supports_parallel_function_calling(self, model: str | None = None) -> bool:
        """Check if the model supports parallel function calling"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_parallel_function_calling(model)

    def supports_images(self, model: str | None = None) -> bool:
        """Check if the model supports image inputs"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_images(model)

    def supports_pdf_input(self, model: str | None = None) -> bool:
        """Check if the model supports PDF inputs"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_pdf_input(model)

    def supports_citations(self, model: str | None = None) -> bool:
        """Check if the model supports citations"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_citations(model)

    def supports_structured_output(self, model: str | None = None) -> bool:
        """Check if the model supports structured output (JSON mode, etc.)"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_structured_output(model)

    def supports_streaming(self, model: str | None = None) -> bool:
        """Check if the model supports streaming responses"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_streaming(model)

    def supports_audio(self, model: str | None = None) -> tuple[bool, bool]:
        """Check if the model supports audio input/output
        Returns: (supports_audio_input, supports_audio_output)
        """
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_audio(model)

    def supports_video(self, model: str | None = None) -> bool:
        """Check if the model supports video inputs"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_video(model)

    def supports_web_search(self, model: str | None = None) -> bool:
        """Check if the model supports web search"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_web_search(model)

    def supports_context_caching(self, model: str | None = None) -> bool:
        """Check if the model supports context/prompt caching"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_context_caching(model)

    def supports_reasoning(self, model: str | None = None) -> bool:
        """Check if the model supports advanced reasoning modes"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.supports_reasoning(model)

    def get_capabilities(self, model: str | None = None) -> dict[str, Any]:
        """Get all capabilities for a model as a dictionary"""
        self._ensure_helpers()
        assert self._capabilities is not None
        return self._capabilities.get_capabilities(model)

    # ==================== Message formatting delegation ====================

    async def format_message_list_for_llm(
        self, messages: list[Message]
    ) -> list[ChatCompletionMessageParam | dict[str, Any]]:
        """Format a list of messages for LLM consumption with event hooks.

        Delegates to MessageFormatter for all formatting logic.
        """
        self._ensure_helpers()
        assert self._formatter is not None
        return await self._formatter.format_message_list_for_llm(messages)

    # ==================== Message creation ====================

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
                    content_parts = (_content,)
                else:
                    content_parts = tuple(_content) if isinstance(_content, list) else _content

        if len(content_parts) == 1 and isinstance(content_parts[0], Message):
            # If a single Message object is passed, set agent and return it directly
            message = content_parts[0]
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
                    from good_agent.content import ImageContentPart

                    image_data = item.get("image_url", {})
                    parts.append(
                        ImageContentPart(
                            image_url=image_data.get("url"),
                            detail=image_data.get("detail", "auto"),
                        )
                    )
            elif isinstance(item, (str, int, float, bool)):
                # Pass raw content for template detection
                parts.append(item)
            else:
                # Assume it's already a content part
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

        ctx = self.agent.events.apply_sync(
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

    # ==================== Configuration ====================

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
    def router(self) -> ManagedRouter:
        """Lazy-loaded ManagedRouter with isolated callbacks"""
        if not self._router:
            # Lazy import factory function only when needed
            from good_agent.model.manager import create_managed_router

            # Get model configuration
            model_name = self.model

            # Create model list for router
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

            # Create ManagedRouter
            self._router = create_managed_router(
                model_list=model_list,
                managed_callbacks=[self],
                routing_strategy="simple-shuffle",
                set_verbose=self._get_config_value("debug", False),
            )

        return self._router

    @property
    def litellm(self) -> Any:
        """Compatibility property - returns litellm module for direct access"""
        if self._litellm is None:
            import litellm

            self._litellm = litellm  # type: ignore[assignment]
        return self._litellm

    @property
    def instructor(self) -> ManagedRouter:
        """Lazy-loaded instructor instance"""
        if self._instructor is None:
            # Get instructor mode from config
            instructor_mode = self._get_config_value("instructor_mode", None)

            # Patch our router with instructor
            self.router.patch_with_instructor(mode=instructor_mode)
            self._instructor_patched = True
            self._instructor = self.router  # type: ignore[assignment]
        assert self._instructor is not None
        return self._instructor

    def _prepare_request_config(self, **kwargs: Unpack[ModelConfig]) -> dict[str, Any]:
        """Prepare configuration for litellm request with model-specific overrides"""
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

        # Ensure we always have a sane timeout
        if config.get("timeout") in (None, "", 0):
            default_timeout = self._get_config_value("timeout", 30.0)
            try:
                from httpx import Timeout as _HTTPXTimeout

                if isinstance(default_timeout, _HTTPXTimeout):
                    total = getattr(default_timeout, "_timeout", None)
                    config["timeout"] = float(total) if total else 30.0
                else:
                    config["timeout"] = float(default_timeout) if default_timeout else 30.0
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
            config.pop("parallel_tool_calls", None)

        # Log if any overrides were applied (for debugging)
        model_override_registry.get_model_info(model_name)

        return config

    def _update_usage(self, response: ModelResponse) -> None:
        """Update usage tracking from response"""
        usage: Usage | None = getattr(response, "usage", None)
        if usage is None:
            return

        # Check if usage has meaningful data (not just defaults)
        if usage.total_tokens > 0:
            self.last_usage = usage
            self.total_tokens += usage.total_tokens

        # Calculate cost if available
        try:
            cost = self.litellm.completion_cost(response)
            if cost:
                self.last_cost = cost
                self.total_cost += cost
        except Exception:
            pass

    # ==================== Core LLM methods ====================

    @overload
    async def complete(
        self,
        messages: Sequence[ChatCompletionMessageParam | dict[str, Any]],
        *,
        stream: Literal[False] = False,
        **kwargs: Unpack[ModelConfig],
    ) -> ModelResponse: ...

    @overload
    async def complete(
        self,
        messages: Sequence[ChatCompletionMessageParam | dict[str, Any]],
        *,
        stream: Literal[True] = True,
        **kwargs: Unpack[ModelConfig],
    ) -> ModelResponse: ...

    async def complete(
        self,
        messages: Sequence[ChatCompletionMessageParam | dict[str, Any]],
        stream: bool = False,
        **kwargs: Unpack[ModelConfig],
    ) -> ModelResponse:
        """Execute LLM chat completion with retry logic and fallback model support.

        Primary method for LLM interactions that handles message formatting,
        model-specific parameter application, automatic retry with exponential
        backoff, fallback model routing, and usage tracking.

        Args:
            messages: Sequence of chat completion messages in litellm format
            stream: Whether to stream the response (default: False)
            **kwargs: Additional model configuration parameters

        Returns:
            ModelResponse with full metadata including choices, usage, and model info

        Raises:
            Exception: When all models (primary + fallbacks) fail
            ValidationError: When message format is invalid for target model
        """
        kwargs["stream"] = stream  # type: ignore[typeddict-item]

        config = self._prepare_request_config(**kwargs)

        # Apply model-specific overrides LAST
        model_name = str(config.get("model", self.model))
        config = model_override_registry.apply(model_name, config)

        # Fire before event
        start_time = time.time()
        from good_agent.core.event_router import EventContext

        ctx: EventContext[CompletionEvent, None] = await self.agent.events.apply_typed(
            AgentEvents.LLM_COMPLETE_BEFORE,
            CompletionEvent,
            None,
            messages=messages,
            config=config,
            llm=self,
        )

        if "parallel_tool_calls" in ctx.parameters["config"] and not ctx.parameters["config"].get(
            "tools"
        ):
            logger.warning("`parallel_tool_calls` added back in")

        try:
            # Router handles retries/fallbacks
            response = await self.router.acompletion(
                messages=ctx.parameters["messages"],
                **ctx.parameters["config"],
            )

            # Fire after event
            end_time = time.time()

            from litellm.types.utils import ModelResponse

            ctx = await self.agent.events.apply_typed(
                AgentEvents.LLM_COMPLETE_AFTER,
                CompletionEvent,
                ModelResponse,  # type: ignore[arg-type]
                output=response,
                config=config,
                llm=self,
            )
            model_response = ctx.return_value
            assert model_response is not None, "After event must return output"
            return model_response
        except (asyncio.CancelledError, KeyboardInterrupt):
            raise
        except Exception as e:
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
        messages: Sequence[ChatCompletionMessageParam],
        response_model: type[BaseModel],
        **kwargs: Unpack[ModelConfig],
    ) -> BaseModel:
        """Extract structured data from LLM responses using instructor library.

        Delegates to StructuredOutputExtractor for all extraction logic.

        Args:
            messages: Sequence of chat messages for extraction context
            response_model: Pydantic BaseModel class for response validation
            **kwargs: Additional model configuration parameters

        Returns:
            Validated instance of the response_model

        Raises:
            ValueError: If instructor returns None instead of BaseModel
            ValidationError: If response cannot be validated against schema
        """
        self._ensure_helpers()
        assert self._extractor is not None
        return await self._extractor.extract(messages, response_model, **kwargs)

    async def stream(
        self,
        messages: Sequence[ChatCompletionMessageParam],
        **kwargs: Unpack[ModelConfig],
    ) -> AsyncIterator[StreamChunk]:
        """Stream a chat completion response token by token.

        Delegates to StreamingHandler for all streaming logic.

        Args:
            messages: Sequence of chat messages
            **kwargs: Additional model configuration options

        Yields:
            StreamChunk: Individual response chunks with content and metadata

        Example:
            >>> async for chunk in llm.stream(messages):
            ...     if chunk.content:
            ...         print(chunk.content, end='', flush=True)
        """
        self._ensure_helpers()
        assert self._streaming is not None
        async for chunk in self._streaming.stream(messages, **kwargs):
            yield chunk

    def _ensure_tool_call_pairs_for_formatted_messages(
        self, messages: Sequence[ChatCompletionMessageParam | dict[str, Any]]
    ) -> list[ChatCompletionMessageParam | dict[str, Any]]:
        """Backward compatibility: Forward to MessageFormatter.

        This method was moved to MessageFormatter during the Phase 2 refactoring.
        Kept here for backward compatibility with tests and any code accessing
        this internal API.

        Args:
            messages: Formatted messages to validate

        Returns:
            Messages with tool call/response pairs ensured
        """
        self._ensure_helpers()
        assert self._formatter is not None
        return self._formatter.ensure_tool_call_pairs_for_formatted_messages(messages)
