from __future__ import annotations

import inspect
import logging
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Protocol,
    Self,
    TypeAlias,
    TypedDict,
    TypeVar,
    cast,
    runtime_checkable,
)
from unittest.mock import MagicMock

import orjson
from pydantic import BaseModel
from ulid import ULID

from good_agent.agent.config import AgentConfigManager
from good_agent.content import TextContentPart
from good_agent.core.components import AgentComponent
from good_agent.messages import (
    Annotation,
    AnnotationLike,
    AssistantMessage,
    AssistantMessageStructuredOutput,
    CitationURL,
    Message,
    MessageContent,
    MessageRole,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from good_agent.model.protocols import StreamChunk
from good_agent.tools import ToolCall, ToolCallFunction, ToolResponse

# Lazy loading litellm types - moved to TYPE_CHECKING
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from litellm.types.utils import Usage

    from good_agent.agent import Agent
    from good_agent.model.llm import LanguageModel

__all__ = [
    # Main mock classes
    "MockAgent",
    "MockResponse",
    "MockToolCall",
    "MockMessage",
    "AgentMockInterface",
    "MockLanguageModel",
    "MockQueuedLanguageModel",
    "MockAgentConfigManager",
    # Handler-based mocking
    "MockContext",
    "MockHandler",
    "MockHandlerLanguageModel",
    "QueuedResponseHandler",
    "ConditionalHandler",
    "TranscriptHandler",
    # Mock creation functions
    "mock_message",
    "mock_tool_call",
    # Helper functions for creating mock components
    "create_citation",
    "create_annotation",
    "create_usage",
    # Factory functions for mock LLMs
    "create_mock_language_model",
    "create_successful_mock_llm",
    "create_failing_mock_llm",
    "create_streaming_mock_llm",
]


class _ToolMessageContextView:
    """Lightweight wrapper exposing augmented tool message content."""

    __slots__ = ("_original", "content", "role")

    def __init__(self, original: ToolMessage, content: str) -> None:
        self._original = original
        self.content = content
        self.role = original.role

    def __getattr__(self, name: str) -> Any:  # pragma: no cover - passthrough
        return getattr(self._original, name)


def _format_tool_message_content(tool_response: ToolResponse) -> str:
    """Render tool responses into message content strings."""

    if not tool_response.success:
        return f"Error: {tool_response.error}"

    if hasattr(tool_response.response, "render") and callable(  # type: ignore[attr-defined]
        tool_response.response.render  # type: ignore[attr-defined]
    ):
        try:
            return tool_response.response.render()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - defensive fallback
            return str(tool_response.response)

    return str(tool_response.response)


def _augment_tool_message_for_context(message: ToolMessage) -> ToolMessage:
    """Return a copy of a tool message with JSON metadata appended to content."""

    tool_response = message.tool_response
    if tool_response is None:
        return message

    payload: dict[str, Any] = {}
    if tool_response.parameters:
        payload["arguments"] = tool_response.parameters

    result_payload: Any = tool_response.response
    if hasattr(result_payload, "model_dump") and callable(  # type: ignore[attr-defined]
        result_payload.model_dump  # type: ignore[attr-defined]
    ):
        try:
            result_payload = result_payload.model_dump()  # type: ignore[call-arg]
        except Exception:  # pragma: no cover - defensive fallback
            result_payload = tool_response.response

    payload["result"] = result_payload

    try:
        json_content = orjson.dumps(payload, option=orjson.OPT_INDENT_2).decode("utf-8")
    except Exception:  # pragma: no cover - fallback when JSON serialization fails
        return message

    base_content = str(message.content)
    if base_content:
        augmented_content = (
            base_content if json_content in base_content else f"{base_content}\n{json_content}"
        )
    else:
        augmented_content = json_content

    if augmented_content == base_content:
        return message

    return cast(ToolMessage, _ToolMessageContextView(message, augmented_content))


class MockToolCall(TypedDict):
    """Configuration for a mock tool call"""

    type: Literal["tool_call"]
    tool_name: str
    arguments: dict[str, Any]
    result: Any


class MockMessage(TypedDict):
    """Configuration for a mock message"""

    type: Literal["message"]
    content: str
    role: Literal["assistant", "user", "system", "tool"]
    tool_calls: list[MockToolCall] | None


@dataclass
class MockResponse:
    """Represents a queued mock response"""

    type: Literal["message", "tool_call"] = "message"
    content: str | None = None
    role: Literal["assistant", "user", "system", "tool"] = "assistant"
    tool_calls: list[MockToolCall] | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: Any = None
    tool_call_id: str | None = None
    # Additional message parameters
    citations: list[CitationURL] | None = None
    annotations: list[AnnotationLike] | None = None
    refusal: str | None = None
    reasoning: str | None = None
    usage: Usage | None = None
    metadata: dict[str, Any] | None = None


TranscriptEntry = (
    tuple[Literal["assistant", "user", "system", "tool"], str]
    | tuple[Literal["assistant", "user", "system", "tool"], str, dict[str, Any]]
)


@dataclass(slots=True)
class _MockModelConfig:
    model: str = "mock-model"


@dataclass(slots=True)
class _MockToolCallFunctionPayload:
    name: str
    arguments: str


@dataclass(slots=True)
class _MockToolCallPayload:
    id: str
    function: _MockToolCallFunctionPayload


@dataclass(slots=True)
class _MockLiteLLMMessage:
    content: str
    tool_calls: list[_MockToolCallPayload] | None = None
    citations: list[CitationURL] | None = None
    annotations: list[AnnotationLike] | None = None
    refusal: str | None = None
    reasoning: str | None = None
    model_extra: dict[str, Any] | None = None


@dataclass(slots=True)
class Choices:
    message: _MockLiteLLMMessage
    provider_specific_fields: dict[str, Any]


@dataclass(slots=True)
class _MockLLMResponse:
    choices: list[Choices]
    usage: Usage
    model: str
    id: str
    created: int


def _build_tool_call_payloads(
    mock_tool_calls: Sequence[MockToolCall],
) -> list[_MockToolCallPayload]:
    return [
        _MockToolCallPayload(
            id=str(ULID()),
            function=_MockToolCallFunctionPayload(
                name=tool_call["tool_name"],
                arguments=orjson.dumps(tool_call["arguments"]).decode(),
            ),
        )
        for tool_call in mock_tool_calls
    ]


def _mock_response_to_llm_response(
    mock_response: MockResponse, model_name: str
) -> _MockLLMResponse:
    tool_calls = (
        _build_tool_call_payloads(mock_response.tool_calls) if mock_response.tool_calls else None
    )

    message = _MockLiteLLMMessage(
        content=mock_response.content or "",
        tool_calls=tool_calls,
        citations=mock_response.citations,
        annotations=mock_response.annotations,
        refusal=mock_response.refusal,
        reasoning=mock_response.reasoning,
        model_extra=mock_response.metadata,
    )

    choice = Choices(
        message=message,
        provider_specific_fields={},
    )

    usage = mock_response.usage
    if usage is None:
        from litellm.types.utils import Usage

        usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)

    return _MockLLMResponse(
        choices=[choice],
        usage=usage,
        model=model_name,
        id=f"mock-{ULID()}",
        created=1234567890,
    )


def mock_message(
    content: str,
    role: Literal["assistant", "user", "system"] = "assistant",
    tool_calls: list[tuple[str, dict[str, Any]]] | None = None,
    citations: list[CitationURL] | None = None,
    annotations: list[AnnotationLike] | None = None,
    refusal: str | None = None,
    reasoning: str | None = None,
    usage: Usage | None = None,
    metadata: dict[str, Any] | None = None,
) -> MockResponse:
    """Create a mock message response with full parameter support"""
    mock_tool_calls = None
    if tool_calls:
        mock_tool_calls = [
            MockToolCall(type="tool_call", tool_name=name, arguments=args, result=None)
            for name, args in tool_calls
        ]

    return MockResponse(
        type="message",
        content=content,
        role=role,
        tool_calls=mock_tool_calls,
        citations=citations,
        annotations=annotations,
        refusal=refusal,
        reasoning=reasoning,
        usage=usage,
        metadata=metadata,
    )


def mock_tool_call(
    tool_name: str, arguments: dict[str, Any] | None = None, result: Any = "Mock result"
) -> MockResponse:
    """Create a mock tool call"""
    return MockResponse(
        type="tool_call",
        tool_name=tool_name,
        tool_arguments=arguments or {},
        tool_result=result,
        tool_call_id=str(ULID()),
    )


# ============================================================================
# Handler-Based Mocking Infrastructure
# ============================================================================


@dataclass
class MockContext:
    """Context passed to mock handlers on each LLM call

    Provides access to agent state, message history, and call metadata
    to help handlers decide what response to return.
    """

    agent: Agent | None
    """Agent making the LLM call, if available."""

    messages: list[Message]
    """Messages being sent to LLM"""

    iteration: int
    """Current execute() iteration number (0-indexed)"""

    call_count: int
    """Total number of LLM calls made during this mock session"""

    kwargs: dict[str, Any] = field(default_factory=dict)
    """Additional kwargs passed to LLM (temperature, model, etc.)"""


SyncHandlerCallable: TypeAlias = Callable[[MockContext], MockResponse | str]
AsyncHandlerCallable: TypeAlias = Callable[[MockContext], Awaitable[MockResponse | str]]
HandlerCallable: TypeAlias = SyncHandlerCallable | AsyncHandlerCallable


@runtime_checkable
class MockHandler(Protocol):
    """Protocol for mock response handlers

    Handlers are called on each LLM completion request and must return
    a MockResponse based on the current context.
    """

    async def handle(self, context: MockContext) -> MockResponse:
        """Generate mock response based on context

        Args:
            context: Full context about the current LLM call

        Returns:
            MockResponse to return instead of calling real LLM
        """
        ...


def _ensure_mock_response(payload: MockResponse | str) -> MockResponse:
    """Convert string or MockResponse to MockResponse"""
    if isinstance(payload, MockResponse):
        return payload
    if isinstance(payload, str):
        return MockResponse(content=payload, role="assistant")
    raise TypeError(
        f"Handler returned invalid type: {type(payload)}. Expected MockResponse or str."
    )


# ============================================================================
# Built-in Handler Implementations
# ============================================================================


class QueuedResponseHandler:
    """Simple FIFO queue of responses (implements current mock behavior as handler)"""

    def __init__(self, *responses: MockResponse | str) -> None:
        self.responses: list[MockResponse] = [_ensure_mock_response(r) for r in responses]
        self.index: int = 0

    async def handle(self, context: MockContext) -> MockResponse:
        if self.index >= len(self.responses):
            raise ValueError(
                f"Mock exhausted: needed response {self.index + 1} "
                f"but only {len(self.responses)} were queued"
            )

        response = self.responses[self.index]
        self.index += 1
        return response


class ConditionalHandler:
    """Match responses based on conditions (content, iteration, etc.)"""

    def __init__(self) -> None:
        self.rules: list[tuple[Callable[[MockContext], bool], MockResponse]] = []
        self.default_response: MockResponse | None = None

    def when(self, condition: Callable[[MockContext], bool], respond: str | MockResponse) -> Self:
        """Add conditional rule"""
        response = _ensure_mock_response(respond)
        self.rules.append((condition, response))
        return self

    def default(self, respond: str | MockResponse) -> Self:
        """Set fallback response"""
        self.default_response = _ensure_mock_response(respond)
        return self

    async def handle(self, context: MockContext) -> MockResponse:
        # Check rules in order
        for condition, response in self.rules:
            if condition(context):
                return response

        # Fallback
        if self.default_response:
            return self.default_response

        raise ValueError("No condition matched and no default set")


class TranscriptHandler:
    """Follow a predefined conversation transcript"""

    def __init__(self, transcript: list[TranscriptEntry]) -> None:
        """
        Args:
            transcript: List of (role, content, **extras) tuples
                Example: [
                    ("assistant", "I'll check weather", {"tool_calls": [...]}),
                    ("assistant", "It's sunny"),
                ]
        """
        self.transcript: list[TranscriptEntry] = transcript
        self.position: int = 0

    async def handle(self, context: MockContext) -> MockResponse:
        if self.position >= len(self.transcript):
            raise ValueError(f"Transcript exhausted at position {self.position}")

        entry = self.transcript[self.position]
        self.position += 1

        # Parse entry
        role, content, *extras = entry
        kwargs = extras[0] if extras else {}

        return MockResponse(content=content, role=role, **kwargs)


class MockHandlerLanguageModel(AgentComponent):
    """Language model that delegates to a handler for mock responses"""

    name = "language_model"

    def __init__(
        self,
        handler: MockHandler | HandlerCallable,
        agent: Agent | None = None,
    ) -> None:
        self.handler: MockHandler | HandlerCallable = handler
        self._agent: Agent | None = agent
        self.call_count: int = 0
        self._local_config: _MockModelConfig = _MockModelConfig()

        # Track API requests/responses like the real LanguageModel
        self.api_requests: list[dict[str, Any]] = []
        self.api_responses: list[Any] = []
        # Aliases with underscores to match real LanguageModel
        self._api_requests: list[dict[str, Any]] = self.api_requests
        self._api_responses: list[Any] = self.api_responses

    @property
    def config(self) -> Any:
        return self._local_config

    async def install(self, agent: Agent) -> None:
        """Install method to satisfy component interface"""
        self._agent = agent

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
        """Mock complete that delegates to handler"""
        self.call_count += 1

        # Track the request
        request_data: dict[str, Any] = {"messages": messages, **kwargs}
        self.api_requests.append(request_data)

        # Fire llm:complete:before event
        if self._agent:
            from good_agent.events import AgentEvents

            await self._agent.events.apply(
                AgentEvents.LLM_COMPLETE_BEFORE,
                messages=messages,
                config=kwargs,
                llm=self,
            )

        # Build context
        agent_messages = self._agent.messages if self._agent else []
        context_messages = [
            _augment_tool_message_for_context(message)
            if isinstance(message, ToolMessage)
            else message
            for message in agent_messages
        ]

        context = MockContext(
            agent=self._agent,
            messages=context_messages,
            iteration=getattr(self._agent, "_iteration_index", 0) if self._agent else 0,
            call_count=self.call_count,
            kwargs=kwargs,
        )

        mock_response = await self._invoke_handler(context)

        # Convert to LiteLLM format
        llm_response = self._to_litellm_response(mock_response)

        # Track response
        self.api_responses.append(llm_response)

        # Fire llm:complete:after event
        if self._agent:
            from good_agent.events import AgentEvents

            await self._agent.events.apply(
                AgentEvents.LLM_COMPLETE_AFTER,
                response=llm_response,
                messages=messages,
                llm=self,
            )

        return llm_response

    async def _invoke_handler(self, context: MockContext) -> MockResponse:
        """Execute the configured handler and normalise the return value."""
        handler = self.handler
        candidate: Any

        if isinstance(handler, MockHandler):
            candidate = handler.handle(context)
        else:
            # It's a callable (function or lambda)
            candidate = handler(context)

        resolved: MockResponse | str
        if inspect.isawaitable(candidate):
            resolved = await candidate
        else:
            resolved = candidate

        return _ensure_mock_response(resolved)

    def _to_litellm_response(self, mock_response: MockResponse) -> Any:
        """Convert MockResponse to LiteLLM format"""
        return _mock_response_to_llm_response(mock_response, self.config.model)

    async def extract(
        self,
        messages: list[dict[str, Any]],
        response_model: type[Any],
        **kwargs: Any,
    ) -> Any:
        """Mock extract for structured output - not implemented yet"""
        raise NotImplementedError("Structured output mocking not yet implemented")

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Mock stream - not implemented yet"""
        raise NotImplementedError("Streaming mock not yet implemented")

    def create_message(
        self,
        *content: MessageContent,
        role: MessageRole = "user",
        output: BaseModel | None = None,
        **kwargs: Any,
    ) -> Message:
        """Create a message based on role type - mimics LanguageModel.create_message"""
        # Cast kwargs to dict[str, Any] to avoid mypy inference issues
        params: dict[str, Any] = kwargs

        content_parts: list[TextContentPart] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    content_parts.append(TextContentPart(text=item.get("text", "")))
            else:
                content_parts.append(TextContentPart(text=str(item)))

        # Convert tool_calls if present
        if role == "assistant" and "tool_calls" in params:
            tool_calls = params["tool_calls"]
            if tool_calls and not isinstance(tool_calls[0], ToolCall):
                converted_tool_calls: list[ToolCall] = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tool_call = ToolCall(
                            id=str(ULID()),
                            function=ToolCallFunction(
                                name=tc["name"],
                                arguments=orjson.dumps(tc["arguments"]).decode(),
                            ),
                        )
                        converted_tool_calls.append(tool_call)
                    elif hasattr(tc, "function"):
                        tool_call = ToolCall(
                            id=str(getattr(tc, "id", ULID())),
                            function=ToolCallFunction(
                                name=tc.function.name,
                                arguments=tc.function.arguments,
                            ),
                        )
                        converted_tool_calls.append(tool_call)
                params["tool_calls"] = converted_tool_calls

        # Create appropriate message type
        if role == "system":
            return SystemMessage(*content_parts, **params)
        elif role == "user":
            return UserMessage(*content_parts, **params)
        elif role == "assistant":
            if output:
                return AssistantMessageStructuredOutput(*content_parts, output=output, **params)
            return AssistantMessage(*content_parts, **params)
        elif role == "tool":
            return ToolMessage(*content_parts, **params)
        else:
            raise ValueError(f"Unknown role: {role}")

    def transform_message_list(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        """Transform agent messages to LLM format"""
        messages_for_llm: list[dict[str, Any]] = []
        for message in messages:
            # Simple transformation to dict format expected by LLMs
            msg_dict: dict[str, Any] = {
                "role": message.role,
                "content": message.content if hasattr(message, "content") else "",
            }
            # Add tool calls if present
            if isinstance(message, AssistantMessage) and message.tool_calls:
                msg_dict["tool_calls"] = message.tool_calls
            messages_for_llm.append(msg_dict)
        return messages_for_llm

    async def format_message_list_for_llm(
        self, messages: Sequence[Message]
    ) -> list[dict[str, Any]]:
        """Async version of transform_message_list"""
        return self.transform_message_list(messages)


class MockQueuedLanguageModel(AgentComponent):
    """Mock language model that returns queued responses instead of calling LLM"""

    name = "language_model"

    def __init__(self, responses: Sequence[MockResponse], agent: Agent | None = None) -> None:
        self.responses: list[MockResponse] = list(responses)
        self.response_index: int = 0
        self._local_config: _MockModelConfig = _MockModelConfig()
        self._agent: Agent | None = agent  # Store agent reference for event firing

        # Track API requests/responses like the real LanguageModel
        self.api_requests: list[dict[str, Any]] = []
        self.api_responses: list[_MockLLMResponse] = []
        # Aliases with underscores to match real LanguageModel
        self._api_requests: list[dict[str, Any]] = self.api_requests
        self._api_responses: list[_MockLLMResponse] = self.api_responses

    @property
    def config(self) -> Any:
        return self._local_config

    async def install(self, agent: Agent) -> None:
        """Install method to satisfy component interface"""
        self._agent = agent

    async def complete(self, messages: list[dict[str, Any]], **kwargs: Any) -> _MockLLMResponse:
        """Mock complete that returns the next queued response"""
        # Track the request just like real LanguageModel does
        request_data: dict[str, Any] = {"messages": messages, **kwargs}
        self.api_requests.append(request_data)

        # Fire llm:complete:before event to match real LanguageModel
        if self._agent:
            from good_agent.events import AgentEvents

            await self._agent.events.apply(
                AgentEvents.LLM_COMPLETE_BEFORE,
                messages=messages,
                config=kwargs,
                llm=self,
            )

        if self.response_index >= len(self.responses):
            logger.error(
                f"Mock LLM exhausted: Attempted to use response {self.response_index + 1} "
                f"but only {len(self.responses)} responses were queued"
            )
            raise ValueError("No more mock responses available")

        response = self.responses[self.response_index]
        self.response_index += 1

        logger.info(
            f"🎭 MOCK LLM CALL #{self.response_index}/{len(self.responses)}: "
            f"Returning mock response instead of calling {kwargs.get('model', 'LLM')}"
        )

        # Log the last user message for context
        if messages:
            last_msg = messages[-1]
            if last_msg.get("role") == "user":
                content_preview = last_msg.get("content", "")[:100]
                logger.debug(
                    f"  User query: {content_preview}{'...' if len(content_preview) == 100 else ''}"
                )

        # Log what we're returning
        content_preview = (response.content or "")[:100] if response.content else "<empty>"
        logger.debug(
            f"  Mock response: {content_preview}{'...' if len(content_preview) == 100 else ''}"
        )

        # Only process assistant messages from the queue
        if response.type != "message" or response.role != "assistant":
            raise ValueError(f"Expected assistant message, got {response.type}:{response.role}")

        mock_llm_response = _mock_response_to_llm_response(response, self.config.model)

        # Track the response just like real LanguageModel does
        self.api_responses.append(mock_llm_response)

        # Fire llm:complete:after event to match real LanguageModel
        if self._agent:
            from good_agent.events import AgentEvents

            await self._agent.events.apply(
                AgentEvents.LLM_COMPLETE_AFTER,
                response=mock_llm_response,
                messages=messages,
                llm=self,
            )

        return mock_llm_response

    @property
    def agent(self) -> Agent:
        """
        Returns the agent this component is installed on.
        """
        assert self._agent is not None, "This component is not installed on an agent"
        return self._agent

    @agent.setter
    def agent(self, value: Agent) -> None:
        self._agent = value

    async def extract(
        self,
        messages: list[dict[str, Any]],
        response_model: type[Any],
        **kwargs: Any,
    ) -> Any:
        """Mock extract for structured output - not implemented yet"""
        raise NotImplementedError("Structured output mocking not yet implemented")

    async def stream(
        self, messages: list[dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[StreamChunk]:
        """Mock stream - not implemented yet"""
        raise NotImplementedError("Streaming mock not yet implemented")

    def create_message(
        self,
        *content: MessageContent,
        role: MessageRole = "user",
        output: BaseModel | None = None,
        **kwargs: Any,
    ) -> Message:
        """Create a message based on role type - mimics LanguageModel.create_message"""

        # Cast kwargs to dict[str, Any] to avoid mypy inference issues
        params: dict[str, Any] = kwargs

        # Extract content from response
        content_parts: list[TextContentPart] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    content_parts.append(TextContentPart(text=item.get("text", "")))
                # Add other content types as needed
            else:
                # Fallback to text
                content_parts.append(TextContentPart(text=str(item)))

        # Convert tool_calls if present and it's an assistant message
        if role == "assistant" and "tool_calls" in params:
            tool_calls = params["tool_calls"]
            if tool_calls and not isinstance(tool_calls[0], ToolCall):
                converted_tool_calls: list[ToolCall] = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        tool_call = ToolCall(
                            id=str(ULID()),
                            function=ToolCallFunction(
                                name=tc["name"],
                                arguments=orjson.dumps(tc["arguments"]).decode(),
                            ),
                        )
                        converted_tool_calls.append(tool_call)
                    elif hasattr(tc, "function"):
                        tool_call = ToolCall(
                            id=str(getattr(tc, "id", ULID())),
                            function=ToolCallFunction(
                                name=tc.function.name,
                                arguments=tc.function.arguments,
                            ),
                        )
                        converted_tool_calls.append(tool_call)
                params["tool_calls"] = converted_tool_calls

        # Create appropriate message type based on role
        if role == "system":
            return SystemMessage(*content_parts, **params)
        elif role == "user":
            return UserMessage(*content_parts, **params)
        elif role == "assistant":
            if output:
                return AssistantMessageStructuredOutput(*content_parts, output=output, **params)
            return AssistantMessage(*content_parts, **params)
        elif role == "tool":
            return ToolMessage(*content_parts, **params)
        else:
            raise ValueError(f"Unknown role: {role}")

    def transform_message_list(self, messages: Sequence[Message]) -> list[dict[str, Any]]:
        """Transform agent messages to LLM format - mimics LanguageModel.transform_message_list"""
        messages_for_llm: list[dict[str, Any]] = []
        for message in messages:
            # Simple transformation to dict format expected by LLMs
            msg_dict: dict[str, Any] = {
                "role": message.role,
                "content": message.content if hasattr(message, "content") else "",
            }
            # Add tool calls if present
            if isinstance(message, AssistantMessage) and message.tool_calls:
                msg_dict["tool_calls"] = message.tool_calls
            messages_for_llm.append(msg_dict)
        return messages_for_llm

    async def format_message_list_for_llm(
        self, messages: Sequence[Message]
    ) -> list[dict[str, Any]]:
        """Async version of transform_message_list to match LanguageModel interface"""
        # For the mock, we just call the sync version
        return self.transform_message_list(messages)


class MockAgent:
    """Mock agent that returns pre-configured responses"""

    def __init__(
        self,
        agent: Agent,
        *responses: MockResponse,
        handler: MockHandler | HandlerCallable | None = None,
    ) -> None:
        self.agent = agent
        self.responses: list[MockResponse] = list(
            responses
        )  # Internal queue - primarily for testing/debugging
        self._response_index: int = 0
        self._original_model: LanguageModel | None = None
        self._mock_model: MockQueuedLanguageModel | MockHandlerLanguageModel | None = None
        self._handler: MockHandler | HandlerCallable | None = handler

    def __enter__(self) -> MockAgent:
        """Enter context manager - replace agent's model with mock"""
        from good_agent.model.llm import LanguageModel

        self._original_model = self.agent.model

        # Create appropriate mock model based on what was provided
        if self._handler is not None:
            # Handler-based mocking
            self._mock_model = MockHandlerLanguageModel(self._handler, agent=self.agent)
            logger.info(
                f"MockAgent activated for agent {self.agent.id} with handler {self._handler.__class__.__name__}"
            )
        else:
            # Queue-based mocking (original behavior)
            self._mock_model = MockQueuedLanguageModel(self.responses, agent=self.agent)
            logger.info(
                f"MockAgent activated for agent {self.agent.id} with {len(self.responses)} queued responses"
            )

        # Replace the LanguageModel component in the agent's extensions
        mock_component = cast(AgentComponent, self._mock_model)
        self.agent._component_registry._extensions[LanguageModel] = mock_component
        self.agent._component_registry._extension_names["LanguageModel"] = mock_component

        logger.debug(
            f"Replaced model {self._original_model.__class__.__name__} with {self._mock_model.__class__.__name__}"
        )

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """Exit context manager - restore original model"""
        from good_agent.model.llm import LanguageModel

        if self._original_model is None:
            raise RuntimeError("MockAgent exited before being entered")

        original_component: AgentComponent = self._original_model

        # Restore the original LanguageModel component
        self.agent._component_registry._extensions[LanguageModel] = original_component
        self.agent._component_registry._extension_names["LanguageModel"] = original_component

        # Log appropriate message based on mock type
        if isinstance(self._mock_model, MockHandlerLanguageModel):
            logger.info(
                f"MockAgent deactivated for agent {self.agent.id}. "
                f"Handler processed {self._mock_model.call_count} LLM calls"
            )
        else:
            responses_used = self._mock_model.response_index if self._mock_model else 0
            logger.info(
                f"MockAgent deactivated for agent {self.agent.id}. "
                f"Used {responses_used}/{len(self.responses)} responses"
            )

        logger.debug(f"Restored original model {self._original_model.__class__.__name__}")

        return False

    async def __aenter__(self) -> MockAgent:
        """Async context manager entry"""
        return self.__enter__()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> Literal[False]:
        """Async context manager exit"""
        return self.__exit__(exc_type, exc_val, exc_tb)

    @property
    def responses_used(self) -> int:
        """Number of responses that have been consumed."""
        if isinstance(self._mock_model, MockQueuedLanguageModel):
            return self._mock_model.response_index
        return 0

    @property
    def responses_remaining(self) -> int:
        """Number of responses still available."""
        return len(self.responses) - self.responses_used

    def all_responses_consumed(self) -> bool:
        """Check if all queued responses have been used."""
        return self.responses_used >= len(self.responses)

    @property
    def api_requests(self) -> list[dict[str, Any]]:
        """Get API requests made during mocking."""
        if self._mock_model is None:
            return []
        return list(self._mock_model.api_requests)

    @property
    def api_responses(self) -> list[_MockLLMResponse]:
        """Get API responses returned during mocking."""
        if self._mock_model is None:
            return []
        return list(self._mock_model.api_responses)

    async def execute(
        self,
        *content_parts: MessageContent,
        role: Literal["user", "assistant", "system", "tool"] = "user",
        context: dict[str, Any] | None = None,
        streaming: bool = False,
        max_iterations: int = 10,
        **kwargs: Any,
    ) -> AsyncIterator[Message]:
        """Execute the agent with mocked responses"""
        # Append input message if provided (matching Agent.execute behavior)
        if content_parts:
            self.agent.append(*content_parts, role=role, context=context)

        # Yield messages based on queued responses following conversation flow rules
        for response in self.responses:
            msg: Message
            if response.type == "message":
                # Create appropriate message type
                if response.role == "assistant":
                    msg = AssistantMessage(
                        content=response.content or "",
                        tool_calls=self._convert_tool_calls(response.tool_calls)
                        if response.tool_calls
                        else None,
                        citations=response.citations,
                        annotations=response.annotations,
                        refusal=response.refusal,
                        reasoning=response.reasoning,
                    )
                elif response.role == "user":
                    msg = UserMessage(content=response.content or "")
                elif response.role == "system":
                    msg = SystemMessage(content=response.content or "")
                else:
                    # Default to assistant
                    msg = AssistantMessage(content=response.content or "")

                # Set execution properties
                msg._i = self._response_index
                msg._set_agent(self.agent)

                yield msg

            elif response.type == "tool_call":
                # Create tool message
                tool_response = ToolResponse(
                    tool_name=response.tool_name or "",
                    tool_call_id=response.tool_call_id,
                    response=response.tool_result,
                    parameters=response.tool_arguments or {},
                    success=True,
                )

                msg = ToolMessage(
                    content=_format_tool_message_content(tool_response),
                    tool_call_id=response.tool_call_id or "",
                    tool_name=response.tool_name or "",
                    tool_response=tool_response,
                )

                # Set execution properties
                msg._i = self._response_index
                msg._set_agent(self.agent)

                yield msg

            self._response_index += 1

    async def call(
        self,
        *content_parts: MessageContent,
        role: Literal["user", "assistant", "system", "tool"] = "user",
        context: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Message:
        """Call the agent with a mocked response

        Delegates to the agent's call() method which will use the mocked LLM.
        Defaults to auto_execute_tools=False to return the first mocked response.
        """
        # Default to not auto-executing tools for predictable mocking
        if "auto_execute_tools" not in kwargs:
            kwargs["auto_execute_tools"] = False

        # Delegate to agent's call() which will use the mocked LanguageModel
        result = await self.agent.call(*content_parts, role=role, context=context, **kwargs)
        return cast(Message, result)

    def _convert_tool_calls(
        self, mock_tool_calls: Sequence[MockToolCall] | None
    ) -> list[ToolCall] | None:
        """Convert MockToolCall objects to ToolCall objects"""
        if not mock_tool_calls:
            return None

        converted: list[ToolCall] = []
        for mtc in mock_tool_calls:
            tool_call = ToolCall(
                id=str(ULID()),
                function=ToolCallFunction(
                    name=mtc["tool_name"],
                    arguments=orjson.dumps(mtc["arguments"]).decode(),
                ),
            )
            converted.append(tool_call)

        return converted


class AgentMockInterface(AgentComponent):
    """
    Mock interface for an agent that supports both:
    - agent.mock() to create mock agent context manager
    - agent.mock.create() to create individual mock messages
    - agent.mock.tool_call() to create mock tool calls
    """

    def __call__(self, *responses: MockResponse | str | MockHandler | Callable) -> MockAgent:
        """
        Create a mock agent context manager.

        Supports:
        - Strings/MockResponse objects: Uses QueuedResponseHandler (current behavior)
        - Handler classes/functions: Uses MockHandlerLanguageModel

        Usage:
            agent.mock(response1, response2, ...)  # Queue-based
            agent.mock(my_handler)  # Handler-based
        """
        # No arguments -> empty queue
        if not responses:
            return MockAgent(self.agent)

        # Single argument that's a handler (has .handle method or is a function)
        if len(responses) == 1:
            item = responses[0]
            # Check if it's a handler instance (has .handle method) or a callable function
            if isinstance(item, MockHandler):
                return MockAgent(self.agent, handler=item)
            if callable(item) and not isinstance(item, (str, MockResponse, type)):
                handler = cast(HandlerCallable, item)
                return MockAgent(self.agent, handler=handler)

        # Multiple args or strings/MockResponses -> use queue handler
        processed_responses: list[MockResponse] = []
        for resp in responses:
            if isinstance(resp, str):
                processed_responses.append(mock_message(resp))
            elif isinstance(resp, MockResponse):
                processed_responses.append(resp)
            else:
                raise TypeError(f"Invalid mock response type: {type(resp)}")

        return MockAgent(self.agent, *processed_responses)

    def create(
        self,
        content: str = "",
        *,
        role: Literal["assistant", "user", "system"] = "assistant",
        tool_calls: list[dict[str, Any]] | None = None,
        citations: list[CitationURL] | None = None,
        annotations: list[AnnotationLike] | None = None,
        refusal: str | None = None,
        reasoning: str | None = None,
        usage: Usage | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MockResponse:
        """
        Create a mock message with full parameter support.

        Usage: agent.mock.create("Response", role="assistant", citations=[...])
        """
        # Convert tool_calls to proper format if provided
        mock_tool_calls = None
        if tool_calls:
            mock_tool_calls = []
            for tc in tool_calls:
                if isinstance(tc, dict) and "name" in tc and "arguments" in tc:
                    mock_tool_calls.append(
                        MockToolCall(
                            type="tool_call",
                            tool_name=tc["name"],
                            arguments=tc["arguments"],
                            result=tc.get("result"),
                        )
                    )
                else:
                    raise ValueError(f"Invalid tool call format: {tc}")

        return MockResponse(
            type="message",
            content=content,
            role=role,
            tool_calls=mock_tool_calls,
            citations=citations,
            annotations=annotations,
            refusal=refusal,
            reasoning=reasoning,
            usage=usage,
            metadata=metadata,
        )

    def tool_call(
        self,
        tool: str,
        *,
        arguments: dict[str, Any] | None = None,
        result: Any = "Mock result",
        **kwargs: Any,
    ) -> MockResponse:
        """
        Create a mock tool call.

        Usage: agent.mock.tool_call("weather", arguments={"location": "NYC"})
        """
        # Support both 'arguments' parameter and **kwargs for arguments
        if arguments is None:
            arguments = kwargs
        else:
            arguments = {**arguments, **kwargs}

        return MockResponse(
            type="tool_call",
            tool_name=tool,
            tool_arguments=arguments,
            tool_result=result,
            tool_call_id=str(ULID()),
        )

    def conditional(self) -> ConditionalHandler:
        """Create a ConditionalHandler for pattern-based responses"""
        return ConditionalHandler()

    def transcript(self, transcript: list[tuple]) -> MockAgent:
        """Create a mock agent using a TranscriptHandler"""
        return MockAgent(self.agent, handler=TranscriptHandler(transcript))


# LLM-specific mocking

T = TypeVar("T", bound=BaseModel)


class MockLanguageModel(AgentComponent):
    """Mock implementation of LanguageModel for testing"""

    name = "language_model"

    def __init__(self, config, **kwargs):
        self._local_config = (
            config if isinstance(config, AgentConfigManager) else MockAgentConfigManager(config)
        )
        self._override_config = kwargs

        # Override lazy loading with mocks
        self._litellm = MagicMock()
        self._instructor = MagicMock()

        # Mock responses
        self.mock_complete_response: Any = None
        self.mock_extract_response: Any = None
        self.mock_stream_chunks: list[Any] = []

        # Track calls
        self.complete_calls = []
        self.extract_calls = []
        self.stream_calls = []

        # Simulate failures
        self.should_fail = False
        self.failure_message = "Mock failure"

        # Mock usage tracking
        self.total_tokens = 0
        self.total_cost = 0.0
        self.last_usage = None
        self.last_cost = None

        # Request/response tracking
        self._api_requests = []
        self._api_responses = []

    @property
    def config(self) -> Any:
        return self._local_config

    def _get_config_value(self, key: str, default: Any = None) -> Any:
        """Mock config value getter"""
        return self._override_config.get(key, self.config.get(key, default))

    @property
    def model(self) -> str:
        return self._get_config_value("model", "mock-model")

    @property
    def temperature(self) -> float:
        return self._get_config_value("temperature", 0.7)

    @property
    def max_retries(self) -> int:
        return self._get_config_value("max_retries", 3)

    @property
    def fallback_models(self) -> list[str]:
        return self._get_config_value("fallback_models", [])

    @property
    def litellm(self):
        return self._litellm

    @property
    def instructor(self):
        return self._instructor

    def set_complete_response(self, response: Any):
        """Set the response for complete() calls"""
        self.mock_complete_response = response

    def set_extract_response(self, response: BaseModel):
        """Set the response for extract() calls"""
        self.mock_extract_response = response

    def set_stream_chunks(self, chunks: list[str]):
        """Set the chunks for stream() calls"""
        self.mock_stream_chunks = [StreamChunk(content=chunk) for chunk in chunks]

    def set_failure(self, should_fail: bool = True, message: str = "Mock failure"):
        """Configure the mock to fail"""
        self.should_fail = should_fail
        self.failure_message = message

    async def complete(self, messages: list[dict[str, Any]], **kwargs) -> Any:
        """Mock complete implementation"""
        self.complete_calls.append({"messages": messages, "kwargs": kwargs})

        if self.should_fail:
            raise Exception(self.failure_message)

        if self.mock_complete_response is None:
            # Default mock response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "Mock response"
            mock_response.usage = MagicMock()
            mock_response.usage.prompt_tokens = 10
            mock_response.usage.completion_tokens = 5
            mock_response.usage.total_tokens = 15
            self.mock_complete_response = mock_response

        # Mock usage tracking
        from litellm.types.utils import Usage

        self.last_usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        self.total_tokens += self.last_usage.total_tokens

        return self.mock_complete_response

    async def extract(self, messages: list[dict[str, Any]], response_model: type[T], **kwargs) -> T:
        """Mock extract implementation"""
        self.extract_calls.append(
            {"messages": messages, "response_model": response_model, "kwargs": kwargs}
        )

        if self.should_fail:
            raise Exception(self.failure_message)

        if self.mock_extract_response is None:
            # Create a default instance of the response model
            try:
                self.mock_extract_response = response_model()
            except Exception:
                # If can't create default instance, return a mock
                self.mock_extract_response = MagicMock(spec=response_model)

        # Cast to T to satisfy type checker
        return cast(T, self.mock_extract_response)

    async def stream(self, messages: list[dict[str, Any]], **kwargs) -> AsyncIterator:
        """Mock stream implementation"""
        self.stream_calls.append({"messages": messages, "kwargs": kwargs})

        if self.should_fail:
            raise Exception(self.failure_message)

        if not self.mock_stream_chunks:
            # Default stream chunks
            self.mock_stream_chunks = [
                StreamChunk(content="Mock "),
                StreamChunk(content="stream "),
                StreamChunk(content="response", finish_reason="stop"),
            ]

        for chunk in self.mock_stream_chunks:
            yield chunk

    def reset_calls(self):
        """Reset call tracking"""
        self.complete_calls = []
        self.extract_calls = []
        self.stream_calls = []

    def get_last_complete_call(self) -> dict[str, Any]:
        """Get the last complete() call"""
        if not self.complete_calls:
            raise ValueError("No complete() calls made")
        return self.complete_calls[-1]

    def get_last_extract_call(self) -> dict[str, Any]:
        """Get the last extract() call"""
        if not self.extract_calls:
            raise ValueError("No extract() calls made")
        return self.extract_calls[-1]

    def get_last_stream_call(self) -> dict[str, Any]:
        """Get the last stream() call"""
        if not self.stream_calls:
            raise ValueError("No stream() calls made")
        return self.stream_calls[-1]


class MockAgentConfigManager:
    """Mock configuration manager for testing"""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {
            "model": "mock-model",
            "temperature": 0.7,
            "max_retries": 3,
            "fallback_models": ["mock-fallback"],
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._config[key]

    def __setitem__(self, key: str, value: Any):
        self._config[key] = value

    def update(self, other: dict[str, Any]):
        self._config.update(other)


# Helper functions for creating mock message components


def create_citation(url: str, title: str | None = None) -> CitationURL:
    """Create a citation URL for mock messages.

    Args:
        url: The URL to cite
        title: Optional title for the citation

    Returns:
        CitationURL object
    """
    from good_agent.core.types import URL

    return URL(url)


def create_annotation(
    text: str, start: int, end: int, metadata: dict[str, Any] | None = None
) -> Annotation:
    """Create an annotation for mock messages.

    Args:
        text: The annotation text
        start: Start position in the message
        end: End position in the message
        metadata: Optional metadata dictionary

    Returns:
        Annotation object
    """
    return Annotation(text=text, start=start, end=end, metadata=metadata or {})


def create_usage(
    prompt_tokens: int = 10, completion_tokens: int = 5, total_tokens: int | None = None
) -> Usage:
    """Create a usage object for mock messages.

    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_tokens: Total tokens (defaults to sum of prompt and completion)

    Returns:
        Usage object
    """
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens
    from litellm.types.utils import Usage

    return Usage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )


def create_mock_language_model(
    complete_response: Any = None,
    extract_response: BaseModel | None = None,
    stream_chunks: list[str] | None = None,
    should_fail: bool = False,
    failure_message: str = "Mock failure",
    config: dict[str, Any] | None = None,
) -> MockLanguageModel:
    """Factory function to create a configured mock language model"""

    mock_config = MockAgentConfigManager(config)
    mock_llm = MockLanguageModel(mock_config)

    if complete_response is not None:
        mock_llm.set_complete_response(complete_response)

    if extract_response is not None:
        mock_llm.set_extract_response(extract_response)

    if stream_chunks is not None:
        mock_llm.set_stream_chunks(stream_chunks)

    if should_fail:
        mock_llm.set_failure(should_fail, failure_message)

    return mock_llm


# Convenience functions for common test scenarios


def create_successful_mock_llm(
    config: dict[str, Any] | None = None,
) -> MockLanguageModel:
    """Create a mock LLM that succeeds with default responses"""
    return create_mock_language_model(config=config)


def create_failing_mock_llm(
    failure_message: str = "Mock failure", config: dict[str, Any] | None = None
) -> MockLanguageModel:
    """Create a mock LLM that always fails"""
    return create_mock_language_model(
        should_fail=True, failure_message=failure_message, config=config
    )


def create_streaming_mock_llm(
    chunks: list[str], config: dict[str, Any] | None = None
) -> MockLanguageModel:
    """Create a mock LLM configured for streaming responses"""
    return create_mock_language_model(stream_chunks=chunks, config=config)
