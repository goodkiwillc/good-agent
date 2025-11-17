from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    TypedDict,
    TypeVar,
    cast,
)
from unittest.mock import MagicMock
import logging

import orjson
from pydantic import BaseModel
from ulid import ULID

from .components import AgentComponent
from .agent.config import AgentConfigManager
from .content import TextContentPart
from .messages import (
    Annotation,
    AssistantMessage,
    AssistantMessageStructuredOutput,
    CitationURL,
    MessageContent,
    MessageRole,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from .model.llm import StreamChunk
from .tools import ToolCall, ToolCallFunction, ToolResponse

# Lazy loading litellm types - moved to TYPE_CHECKING
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from litellm.utils import Usage

    from .agent import Agent

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

    type: Literal["message", "tool_call"]
    content: str | None = None
    role: Literal["assistant", "user", "system", "tool"] = "assistant"
    tool_calls: list[MockToolCall] | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    tool_result: Any = None
    tool_call_id: str | None = None
    # Additional message parameters
    citations: list[CitationURL] | None = None
    annotations: list[Annotation] | None = None
    refusal: str | None = None
    reasoning: str | None = None
    usage: "Usage | None" = None
    metadata: dict[str, Any] | None = None


def mock_message(
    content: str,
    role: Literal["assistant", "user", "system"] = "assistant",
    tool_calls: list[tuple[str, dict[str, Any]]] | None = None,
    citations: list[CitationURL] | None = None,
    annotations: list[Annotation] | None = None,
    refusal: str | None = None,
    reasoning: str | None = None,
    usage: "Usage | None" = None,
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


class MockQueuedLanguageModel:
    """Mock language model that returns queued responses instead of calling LLM"""

    def __init__(self, responses: list[MockResponse], agent=None):
        self.responses = responses
        self.response_index = 0
        self.config = MagicMock()
        self.config.model = "mock-model"
        self.agent = agent  # Store agent reference for event firing

        # Track API requests/responses like the real LanguageModel
        self.api_requests: list[Any] = []
        self.api_responses: list[Any] = []
        # Aliases with underscores to match real LanguageModel
        self._api_requests = self.api_requests
        self._api_responses = self.api_responses

    async def complete(self, messages: list[dict[str, Any]], **kwargs) -> Any:
        """Mock complete that returns the next queued response"""
        # Track the request just like real LanguageModel does
        request_data = {"messages": messages, **kwargs}
        self.api_requests.append(request_data)

        # Fire llm:complete:before event to match real LanguageModel
        if self.agent:
            from .events import AgentEvents

            self.agent.do(
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
        content_preview = (
            (response.content or "")[:100] if response.content else "<empty>"
        )
        logger.debug(
            f"  Mock response: {content_preview}{'...' if len(content_preview) == 100 else ''}"
        )

        # Only process assistant messages from the queue
        if response.type != "message" or response.role != "assistant":
            raise ValueError(
                f"Expected assistant message, got {response.type}:{response.role}"
            )

        # Create a mock LLM response structure that matches what the agent expects
        # Create a proper Choices object and Message
        # Create mock message object
        from litellm.utils import Message as LiteLLMMessage

        message = LiteLLMMessage()
        message.content = response.content or ""

        # Add tool calls if present
        if response.tool_calls:
            tool_calls = []
            for tc in response.tool_calls:
                tool_call = MagicMock()
                tool_call.id = str(ULID())
                tool_call.function = MagicMock()
                tool_call.function.name = tc["tool_name"]
                tool_call.function.arguments = orjson.dumps(tc["arguments"]).decode()
                tool_calls.append(tool_call)
            message.tool_calls = tool_calls  # type: ignore[assignment]
        else:
            message.tool_calls = None

        # Add refusal if present (using setattr for dynamic attribute)
        if response.refusal:
            message.refusal = response.refusal  # type: ignore[attr-defined]

        # Create the Choices object
        # Create mock choice object
        from litellm.utils import Choices

        choice = Choices()
        choice.message = message
        choice.provider_specific_fields = {}

        # Debug logging
        logger.debug(
            f"Created choice type: {type(choice)}, isinstance Choices: {isinstance(choice, Choices)}"
        )

        # Create the response object
        mock_llm_response = MagicMock()
        mock_llm_response.choices = [choice]

        # Add usage if present
        if response.usage:
            mock_llm_response.usage = response.usage
        else:
            # Default usage for mocks
            from litellm.utils import Usage

            usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
            mock_llm_response.usage = usage

        # Add metadata that might be expected
        mock_llm_response.model = self.config.model
        mock_llm_response.id = f"mock-{str(ULID())}"
        mock_llm_response.created = 1234567890  # Mock timestamp

        # Track the response just like real LanguageModel does
        self.api_responses.append(mock_llm_response)

        # Fire llm:complete:after event to match real LanguageModel
        if self.agent:
            from .events import AgentEvents

            self.agent.do(
                AgentEvents.LLM_COMPLETE_AFTER,
                response=mock_llm_response,
                messages=messages,
                llm=self,
            )

        return mock_llm_response

    async def extract(
        self, messages: list[dict[str, Any]], response_model: type[Any], **kwargs
    ) -> Any:
        """Mock extract for structured output - not implemented yet"""
        raise NotImplementedError("Structured output mocking not yet implemented")

    async def stream(self, messages: list[dict[str, Any]], **kwargs) -> AsyncIterator:
        """Mock stream - not implemented yet"""
        raise NotImplementedError("Streaming mock not yet implemented")

    def create_message(
        self,
        *content: MessageContent,
        role: MessageRole = "user",
        output: BaseModel | None = None,
        **kwargs: Any,
    ) -> Any:
        """Create a message based on role type - mimics LanguageModel.create_message"""

        # Extract content from response
        content_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    content_parts.append(TextContentPart(text=item.get("text", "")))
                # Add other content types as needed
            else:
                # Fallback to text
                content_parts.append(TextContentPart(text=str(item)))

        # Convert tool_calls if present and it's an assistant message
        if role == "assistant" and "tool_calls" in kwargs:
            tool_calls = kwargs["tool_calls"]
            if tool_calls and not isinstance(tool_calls[0], ToolCall):
                # Convert MagicMock or dict tool_calls to proper ToolCall objects
                converted_tool_calls = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        # Handle dict format: {"name": "func", "arguments": {...}}
                        tool_call = ToolCall(
                            id=str(ULID()),
                            function=ToolCallFunction(
                                name=tc["name"],
                                arguments=orjson.dumps(tc["arguments"]).decode(),
                            ),
                        )
                        converted_tool_calls.append(tool_call)
                    else:
                        # Handle MagicMock objects (convert from existing structure)
                        if hasattr(tc, "function"):
                            tool_call = ToolCall(
                                id=str(tc.id) if hasattr(tc, "id") else str(ULID()),
                                function=ToolCallFunction(
                                    name=tc.function.name,
                                    arguments=tc.function.arguments,
                                ),
                            )
                            converted_tool_calls.append(tool_call)
                kwargs["tool_calls"] = converted_tool_calls

        # Create appropriate message type based on role
        if role == "system":
            return SystemMessage(*content_parts, **kwargs)
        elif role == "user":
            return UserMessage(*content_parts, **kwargs)
        elif role == "assistant":
            if output:
                return AssistantMessageStructuredOutput(
                    *content_parts, output=output, **kwargs
                )
            return AssistantMessage(*content_parts, **kwargs)
        elif role == "tool":
            return ToolMessage(*content_parts, **kwargs)
        else:
            raise ValueError(f"Unknown role: {role}")

    def transform_message_list(self, messages: list) -> list[dict[str, Any]]:
        """Transform agent messages to LLM format - mimics LanguageModel.transform_message_list"""
        messages_for_llm = []
        for message in messages:
            # Simple transformation to dict format expected by LLMs
            msg_dict = {
                "role": message.role,
                "content": message.content if hasattr(message, "content") else "",
            }
            # Add tool calls if present
            if hasattr(message, "tool_calls") and message.tool_calls:
                msg_dict["tool_calls"] = message.tool_calls
            messages_for_llm.append(msg_dict)
        return messages_for_llm

    async def format_message_list_for_llm(self, messages: list) -> list[dict[str, Any]]:
        """Async version of transform_message_list to match LanguageModel interface"""
        # For the mock, we just call the sync version
        return self.transform_message_list(messages)


class MockAgent:
    """Mock agent that returns pre-configured responses"""

    def __init__(self, agent: "Agent", *responses: MockResponse):
        self.agent = agent
        self.responses = list(
            responses
        )  # Internal queue - primarily for testing/debugging
        self._response_index = 0
        self._original_model: Any = None
        self._mock_model: Any = None

    def __enter__(self):
        """Enter context manager - replace agent's model with mock"""
        from .model.llm import LanguageModel

        self._original_model = self.agent.model

        # Create a mock model that returns our queued responses
        self._mock_model = MockQueuedLanguageModel(self.responses, agent=self.agent)

        # Replace the LanguageModel component in the agent's extensions
        self.agent._component_registry._extensions[LanguageModel] = self._mock_model
        self.agent._component_registry._extension_names["LanguageModel"] = (
            self._mock_model
        )

        logger.info(
            f"MockAgent activated for agent {self.agent.id} with {len(self.responses)} queued responses"
        )
        logger.debug(
            f"Replaced model {self._original_model.__class__.__name__} with MockQueuedLanguageModel"
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager - restore original model"""
        from .model.llm import LanguageModel

        # Restore the original LanguageModel component
        self.agent._component_registry._extensions[LanguageModel] = self._original_model
        self.agent._component_registry._extension_names["LanguageModel"] = (
            self._original_model
        )

        responses_used = self._mock_model.response_index if self._mock_model else 0
        logger.info(
            f"MockAgent deactivated for agent {self.agent.id}. "
            f"Used {responses_used}/{len(self.responses)} responses"
        )
        logger.debug(
            f"Restored original model {self._original_model.__class__.__name__}"
        )

        return False

    async def __aenter__(self):
        """Async context manager entry"""
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        return self.__exit__(exc_type, exc_val, exc_tb)

    @property
    def responses_used(self) -> int:
        """Number of responses that have been consumed."""
        if self._mock_model:
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
    def api_requests(self) -> list[Any]:
        """Get API requests made during mocking."""
        if self._mock_model:
            return self._mock_model.api_requests
        return []

    @property
    def api_responses(self) -> list[Any]:
        """Get API responses returned during mocking."""
        if self._mock_model:
            return self._mock_model.api_responses
        return []

    async def execute(self):
        """Execute the agent with mocked responses"""
        # Yield messages based on queued responses following conversation flow rules
        for response in self.responses:
            msg: Any  # Declare variable type once
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
                    content=str(response.tool_result),
                    tool_call_id=response.tool_call_id or "",
                    tool_name=response.tool_name or "",
                    tool_response=tool_response,
                )

                # Set execution properties
                msg._i = self._response_index
                msg._set_agent(self.agent)

                yield msg

            self._response_index += 1

    async def call(self, **kwargs):
        """Call the agent with a mocked response"""
        # Return the first queued response as appropriate message type
        if not self.responses:
            raise ValueError("No mock responses available")

        response = self.responses[0]

        if response.type == "message" and response.role == "assistant":
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

            # Set execution properties
            msg._i = 0
            msg._set_agent(self.agent)

            return msg
        else:
            raise ValueError(
                f"call() expects assistant message response, got {response.type}:{response.role}"
            )

    def _convert_tool_calls(self, mock_tool_calls):
        """Convert MockToolCall objects to ToolCall objects"""
        if not mock_tool_calls:
            return None

        converted = []
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

    def __call__(self, *responses: MockResponse | str):
        """
        Create a mock agent context manager.

        Usage: agent.mock(response1, response2, ...)
        """
        # Convert any raw strings to MockResponse objects
        processed_responses = []
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
        annotations: list[Annotation] | None = None,
        refusal: str | None = None,
        reasoning: str | None = None,
        usage: "Usage | None" = None,
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


# LLM-specific mocking

T = TypeVar("T", bound=BaseModel)


class MockLanguageModel:
    """Mock implementation of LanguageModel for testing"""

    def __init__(self, config, **kwargs):
        self.config = (
            config
            if isinstance(config, AgentConfigManager)
            else MockAgentConfigManager(config)
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
        from litellm.utils import Usage

        self.last_usage = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        self.total_tokens += self.last_usage.total_tokens

        return self.mock_complete_response

    async def extract(
        self, messages: list[dict[str, Any]], response_model: type[T], **kwargs
    ) -> T:
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
) -> "Usage":
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
    from litellm.utils import Usage

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
