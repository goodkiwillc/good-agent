# Test Implementation Examples

## Complete Test File Examples

These are production-ready test files you can use as templates for the new LLM client.

## File: `tests/unit/llm_client/conftest.py`

```python
"""Unit test fixtures for LLM client.

Provides reusable mocks and fixtures for fast, isolated unit testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import Any


# ============================================================================
# Mock Response Builders
# ============================================================================

@pytest.fixture
def openai_response_builder():
    """Factory for building mock OpenAI responses."""
    def build(
        content: str = "Test response",
        model: str = "gpt-4o-mini",
        tool_calls: list[dict] | None = None,
        prompt_tokens: int = 10,
        completion_tokens: int = 5,
    ):
        """Build a mock OpenAI response."""
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-test123"
        mock_response.created = 1234567890
        mock_response.model = model
        mock_response.system_fingerprint = "fp_test"
        
        # Build message
        mock_message = MagicMock()
        mock_message.role = "assistant"
        mock_message.content = content
        mock_message.tool_calls = []
        
        if tool_calls:
            for tc in tool_calls:
                tool_call = MagicMock()
                tool_call.id = tc.get("id", "call_test")
                tool_call.type = tc.get("type", "function")
                tool_call.function = MagicMock()
                tool_call.function.name = tc["function"]["name"]
                tool_call.function.arguments = tc["function"]["arguments"]
                mock_message.tool_calls.append(tool_call)
        else:
            mock_message.tool_calls = None
        
        # Build choice
        mock_choice = MagicMock()
        mock_choice.index = 0
        mock_choice.message = mock_message
        mock_choice.finish_reason = "tool_calls" if tool_calls else "stop"
        
        mock_response.choices = [mock_choice]
        
        # Build usage
        mock_usage = MagicMock()
        mock_usage.prompt_tokens = prompt_tokens
        mock_usage.completion_tokens = completion_tokens
        mock_usage.total_tokens = prompt_tokens + completion_tokens
        mock_response.usage = mock_usage
        
        return mock_response
    
    return build


@pytest.fixture
def streaming_chunk_builder():
    """Factory for building mock streaming chunks."""
    def build(
        content: str | None = None,
        finish_reason: str | None = None,
        model: str = "gpt-4o-mini",
        role: str | None = None,
    ):
        """Build a mock streaming chunk."""
        mock_chunk = MagicMock()
        mock_chunk.id = "chatcmpl-stream123"
        mock_chunk.created = 1234567890
        mock_chunk.model = model
        
        mock_delta = MagicMock()
        mock_delta.role = role
        mock_delta.content = content
        mock_delta.tool_calls = None
        
        mock_choice = MagicMock()
        mock_choice.index = 0
        mock_choice.delta = mock_delta
        mock_choice.finish_reason = finish_reason
        
        mock_chunk.choices = [mock_choice]
        
        return mock_chunk
    
    return build


@pytest.fixture
def anthropic_response_builder():
    """Factory for building mock Anthropic responses."""
    def build(
        content: str = "Test response",
        model: str = "claude-3.5-sonnet",
        input_tokens: int = 10,
        output_tokens: int = 5,
    ):
        """Build a mock Anthropic response."""
        mock_response = MagicMock()
        mock_response.id = "msg_test123"
        mock_response.type = "message"
        mock_response.role = "assistant"
        mock_response.model = model
        mock_response.stop_reason = "end_turn"
        
        # Anthropic uses content blocks
        mock_content = MagicMock()
        mock_content.type = "text"
        mock_content.text = content
        mock_response.content = [mock_content]
        
        # Usage
        mock_usage = MagicMock()
        mock_usage.input_tokens = input_tokens
        mock_usage.output_tokens = output_tokens
        mock_response.usage = mock_usage
        
        return mock_response
    
    return build


# ============================================================================
# Mock SDK Clients
# ============================================================================

@pytest.fixture
def mock_openai_sdk():
    """Mock OpenAI SDK client."""
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock()
    return mock_client


@pytest.fixture
def mock_anthropic_sdk():
    """Mock Anthropic SDK client."""
    mock_client = MagicMock()
    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock()
    return mock_client


@pytest.fixture
def mock_tiktoken_encoding():
    """Mock tiktoken encoding."""
    mock_encoding = MagicMock()
    # Default: return token list of same length as text
    mock_encoding.encode = MagicMock(side_effect=lambda text: list(range(len(text) // 4)))
    return mock_encoding


# ============================================================================
# Provider Clients with Mocked SDKs
# ============================================================================

@pytest.fixture
def openai_client(mock_openai_sdk):
    """OpenAI client with mocked SDK."""
    from good_agent.llm_client.providers.openai import OpenAIClient
    from good_agent.llm_client.base import ClientConfig
    
    config = ClientConfig(api_key="test-key")
    client = OpenAIClient(config=config)
    client._client = mock_openai_sdk  # Inject mock
    return client


@pytest.fixture
def anthropic_client(mock_anthropic_sdk):
    """Anthropic client with mocked SDK."""
    from good_agent.llm_client.providers.anthropic import AnthropicClient
    from good_agent.llm_client.base import ClientConfig
    
    config = ClientConfig(api_key="test-key")
    client = AnthropicClient(config=config)
    client._client = mock_anthropic_sdk  # Inject mock
    return client


# ============================================================================
# Router with Mocked Clients
# ============================================================================

@pytest.fixture
def mock_router_clients():
    """Mock clients for router testing."""
    mock_primary = MagicMock()
    mock_primary.complete = AsyncMock()
    mock_primary.stream = AsyncMock()
    
    mock_fallback = MagicMock()
    mock_fallback.complete = AsyncMock()
    mock_fallback.stream = AsyncMock()
    
    return {
        "primary": mock_primary,
        "fallback": mock_fallback,
    }


@pytest.fixture
def router(mock_router_clients):
    """Router with mocked clients."""
    from good_agent.llm_client.router import ModelRouter
    
    router = ModelRouter(
        primary_model="gpt-4o-mini",
        fallback_models=["gpt-3.5-turbo"],
        max_retries_per_model=2,
        retry_delay=0.01,  # Fast for testing
    )
    
    # Inject mocked clients
    router._clients = {
        "openai": mock_router_clients["primary"],
    }
    
    return router


# ============================================================================
# Sample Test Data
# ============================================================================

@pytest.fixture
def sample_messages():
    """Standard test messages."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]


@pytest.fixture
def sample_messages_with_tools():
    """Messages with tool call results."""
    return [
        {"role": "user", "content": "What's the weather in SF?"},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"location": "San Francisco"}'
                    }
                }
            ]
        },
        {
            "role": "tool",
            "tool_call_id": "call_123",
            "content": '{"temperature": 68, "condition": "sunny"}'
        }
    ]


@pytest.fixture
def sample_tools():
    """Sample tool definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name"
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]


# ============================================================================
# Patching Helpers
# ============================================================================

@pytest.fixture
def patch_tiktoken(mock_tiktoken_encoding):
    """Patch tiktoken for token counting tests."""
    with patch('good_agent.llm_client.tokens.tiktoken') as mock_tiktoken:
        mock_tiktoken.encoding_for_model.return_value = mock_tiktoken_encoding
        mock_tiktoken.get_encoding.return_value = mock_tiktoken_encoding
        yield mock_tiktoken


@pytest.fixture
def patch_cost_database():
    """Patch cost database loading."""
    mock_costs = {
        "gpt-4o-mini": {"input": 0.00000015, "output": 0.0000006},
        "gpt-4": {"input": 0.00003, "output": 0.00006},
        "claude-3.5-sonnet": {"input": 0.000003, "output": 0.000015},
    }
    
    with patch('good_agent.llm_client.costs._load_cost_database') as mock_load:
        mock_load.return_value = mock_costs
        # Also set the module-level cache
        with patch('good_agent.llm_client.costs._cost_database', mock_costs):
            yield mock_costs
```

## File: `tests/unit/llm_client/test_comprehensive.py`

```python
"""Comprehensive unit tests demonstrating all testing patterns.

This file shows complete examples of:
- Response mocking
- Error handling
- Async operations
- Edge cases
- Parameter validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio

from good_agent.llm_client.exceptions import (
    ProviderError,
    RateLimitError,
    AuthenticationError,
    TimeoutError as ClientTimeoutError,
)
from good_agent.llm_client.types import ModelResponse, StreamChunk, Usage


class TestOpenAIClientComprehensive:
    """Comprehensive OpenAI client tests."""
    
    @pytest.mark.asyncio
    async def test_complete_success(
        self, 
        openai_client, 
        mock_openai_sdk,
        openai_response_builder,
        sample_messages
    ):
        """Test successful completion."""
        # Arrange
        mock_response = openai_response_builder(
            content="Hello! How can I help?",
            prompt_tokens=20,
            completion_tokens=10
        )
        mock_openai_sdk.chat.completions.create.return_value = mock_response
        
        # Act
        response = await openai_client.complete(
            messages=sample_messages,
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        # Assert
        assert isinstance(response, ModelResponse)
        assert response.id == "chatcmpl-test123"
        assert response.model == "gpt-4o-mini"
        assert response.choices[0].message.content == "Hello! How can I help?"
        assert response.usage.total_tokens == 30
        assert response._response_ms is not None
        
        # Verify SDK was called correctly
        mock_openai_sdk.chat.completions.create.assert_called_once_with(
            messages=sample_messages,
            model="gpt-4o-mini",
            temperature=0.7
        )
    
    @pytest.mark.asyncio
    async def test_complete_with_tool_calling(
        self,
        openai_client,
        mock_openai_sdk,
        openai_response_builder,
        sample_messages,
        sample_tools
    ):
        """Test completion with function/tool calling."""
        # Arrange
        tool_call = {
            "id": "call_abc123",
            "function": {
                "name": "get_weather",
                "arguments": '{"location": "San Francisco"}'
            }
        }
        mock_response = openai_response_builder(
            content="",
            tool_calls=[tool_call]
        )
        mock_openai_sdk.chat.completions.create.return_value = mock_response
        
        # Act
        response = await openai_client.complete(
            messages=sample_messages,
            model="gpt-4o-mini",
            tools=sample_tools
        )
        
        # Assert
        assert response.choices[0].message.tool_calls is not None
        assert len(response.choices[0].message.tool_calls) == 1
        tool_call_result = response.choices[0].message.tool_calls[0]
        assert tool_call_result["id"] == "call_abc123"
        assert tool_call_result["function"]["name"] == "get_weather"
        assert "location" in tool_call_result["function"]["arguments"]
    
    @pytest.mark.asyncio
    async def test_complete_rate_limit_error(
        self,
        openai_client,
        mock_openai_sdk,
        sample_messages
    ):
        """Test rate limit error handling."""
        from openai import RateLimitError as OpenAIRateLimitError
        
        # Arrange
        mock_openai_sdk.chat.completions.create.side_effect = \
            OpenAIRateLimitError("Rate limit exceeded", response=None, body=None)
        
        # Act & Assert
        with pytest.raises(RateLimitError) as exc_info:
            await openai_client.complete(
                messages=sample_messages,
                model="gpt-4o-mini"
            )
        
        assert "rate limit" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_complete_authentication_error(
        self,
        openai_client,
        mock_openai_sdk,
        sample_messages
    ):
        """Test authentication error handling."""
        from openai import AuthenticationError as OpenAIAuthError
        
        # Arrange
        mock_openai_sdk.chat.completions.create.side_effect = \
            OpenAIAuthError("Invalid API key", response=None, body=None)
        
        # Act & Assert
        with pytest.raises(AuthenticationError):
            await openai_client.complete(
                messages=sample_messages,
                model="gpt-4o-mini"
            )
    
    @pytest.mark.asyncio
    async def test_stream_complete_response(
        self,
        openai_client,
        mock_openai_sdk,
        streaming_chunk_builder,
        sample_messages
    ):
        """Test streaming with multiple chunks."""
        # Arrange
        async def mock_stream():
            yield streaming_chunk_builder(content="Hello", role="assistant")
            yield streaming_chunk_builder(content=" world")
            yield streaming_chunk_builder(content="!")
            yield streaming_chunk_builder(content=None, finish_reason="stop")
        
        mock_openai_sdk.chat.completions.create.return_value = mock_stream()
        
        # Act
        chunks = []
        async for chunk in openai_client.stream(
            messages=sample_messages,
            model="gpt-4o-mini"
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 4
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " world"
        assert chunks[2].content == "!"
        assert chunks[3].finish_reason == "stop"
        
        # Reconstruct full message
        full_content = "".join(c.content for c in chunks if c.content)
        assert full_content == "Hello world!"
    
    @pytest.mark.asyncio
    async def test_stream_with_tool_calls(
        self,
        openai_client,
        mock_openai_sdk,
        sample_messages
    ):
        """Test streaming with tool call chunks."""
        # Arrange
        async def mock_stream():
            # Tool call comes in multiple chunks
            chunk1 = MagicMock()
            chunk1.id = "chatcmpl-stream"
            chunk1.created = 12345
            chunk1.model = "gpt-4o-mini"
            
            delta1 = MagicMock()
            delta1.role = "assistant"
            delta1.content = None
            tool_call1 = MagicMock()
            tool_call1.index = 0
            tool_call1.id = "call_123"
            tool_call1.type = "function"
            tool_call1.function = MagicMock(name="get_weather", arguments="")
            delta1.tool_calls = [tool_call1]
            
            choice1 = MagicMock()
            choice1.index = 0
            choice1.delta = delta1
            choice1.finish_reason = None
            chunk1.choices = [choice1]
            
            yield chunk1
            
            # Arguments come in next chunk
            chunk2 = MagicMock()
            chunk2.id = "chatcmpl-stream"
            chunk2.created = 12345
            chunk2.model = "gpt-4o-mini"
            
            delta2 = MagicMock()
            delta2.role = None
            delta2.content = None
            tool_call2 = MagicMock()
            tool_call2.index = 0
            tool_call2.id = None
            tool_call2.type = None
            tool_call2.function = MagicMock(name=None, arguments='{"location": "SF"}')
            delta2.tool_calls = [tool_call2]
            
            choice2 = MagicMock()
            choice2.index = 0
            choice2.delta = delta2
            choice2.finish_reason = "tool_calls"
            chunk2.choices = [choice2]
            
            yield chunk2
        
        mock_openai_sdk.chat.completions.create.return_value = mock_stream()
        
        # Act
        chunks = []
        async for chunk in openai_client.stream(
            messages=sample_messages,
            model="gpt-4o-mini"
        ):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 2
        assert chunks[1].finish_reason == "tool_calls"
    
    def test_supports_streaming(self, openai_client):
        """Test streaming support detection."""
        assert openai_client.supports_streaming("gpt-4o-mini") is True
        assert openai_client.supports_streaming("gpt-4") is True
        assert openai_client.supports_streaming("gpt-3.5-turbo") is True
        assert openai_client.supports_streaming("o1-preview") is False
        assert openai_client.supports_streaming("o1-mini") is False
    
    def test_supports_tools(self, openai_client):
        """Test tool calling support detection."""
        assert openai_client.supports_tools("gpt-4o-mini") is True
        assert openai_client.supports_tools("gpt-4") is True
        assert openai_client.supports_tools("o1-preview") is True
    
    def test_count_tokens(self, openai_client, patch_tiktoken):
        """Test token counting with tiktoken."""
        # Arrange
        mock_encoding = patch_tiktoken.encoding_for_model.return_value
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        
        # Act
        count = openai_client.count_tokens("Hello world", "gpt-4o-mini")
        
        # Assert
        assert count == 5
        patch_tiktoken.encoding_for_model.assert_called_once_with("gpt-4o-mini")
    
    def test_count_tokens_caching(self, openai_client, patch_tiktoken):
        """Test that tokenizer is cached per model."""
        # Arrange
        mock_encoding = patch_tiktoken.encoding_for_model.return_value
        mock_encoding.encode.return_value = [1, 2, 3]
        
        # Act
        openai_client.count_tokens("test1", "gpt-4o-mini")
        openai_client.count_tokens("test2", "gpt-4o-mini")
        openai_client.count_tokens("test3", "gpt-4o-mini")
        
        # Assert - should only load encoding once
        assert patch_tiktoken.encoding_for_model.call_count == 1
    
    def test_count_tokens_fallback_unknown_model(self, openai_client):
        """Test fallback for unknown model."""
        with patch('good_agent.llm_client.providers.openai.tiktoken') as mock_tik:
            # First call (encoding_for_model) fails
            mock_tik.encoding_for_model.side_effect = KeyError("Unknown model")
            
            # Second call (get_encoding) succeeds
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3]
            mock_tik.get_encoding.return_value = mock_encoding
            
            count = openai_client.count_tokens("test", "custom-model-123")
            
            assert count == 3
            mock_tik.get_encoding.assert_called_once_with("cl100k_base")


class TestModelRouterComprehensive:
    """Comprehensive router tests."""
    
    @pytest.mark.asyncio
    async def test_complete_primary_success(
        self,
        router,
        mock_router_clients,
        sample_messages
    ):
        """Test successful completion with primary model."""
        # Arrange
        expected_response = ModelResponse(
            id="test123",
            created=12345,
            model="gpt-4o-mini",
            choices=[],
            object="chat.completion"
        )
        mock_router_clients["primary"].complete.return_value = expected_response
        
        # Act
        response = await router.complete(sample_messages)
        
        # Assert
        assert response.id == "test123"
        assert router.stats["successful_calls"] == 1
        assert router.stats["fallback_uses"] == 0
        mock_router_clients["primary"].complete.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_complete_fallback_on_provider_error(
        self,
        router,
        mock_router_clients,
        sample_messages
    ):
        """Test fallback to secondary model on provider error."""
        # Arrange
        # Primary fails
        mock_router_clients["primary"].complete.side_effect = ProviderError("API down")
        
        # Need to add fallback client
        mock_fallback = MagicMock()
        mock_fallback.complete = AsyncMock(return_value=ModelResponse(
            id="fallback123",
            created=12345,
            model="gpt-3.5-turbo",
            choices=[],
            object="chat.completion"
        ))
        
        # Mock get_client to return our mocks
        with patch.object(router, '_get_client') as mock_get:
            def get_client_side_effect(model):
                if "gpt-4o-mini" in model:
                    return mock_router_clients["primary"]
                elif "gpt-3.5-turbo" in model:
                    return mock_fallback
            
            mock_get.side_effect = get_client_side_effect
            
            # Act
            response = await router.complete(sample_messages)
        
        # Assert
        assert response.id == "fallback123"
        assert router.stats["fallback_uses"] == 1
        assert router.stats["successful_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_complete_retry_with_backoff(
        self,
        router,
        mock_router_clients,
        sample_messages
    ):
        """Test retry with exponential backoff on rate limit."""
        # Arrange
        call_count = 0
        
        async def mock_complete_with_retries(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RateLimitError("Rate limited")
            return ModelResponse(
                id="success",
                created=12345,
                model="gpt-4o-mini",
                choices=[],
                object="chat.completion"
            )
        
        mock_router_clients["primary"].complete = mock_complete_with_retries
        
        # Act
        with patch('asyncio.sleep') as mock_sleep:
            response = await router.complete(sample_messages)
        
        # Assert
        assert response.id == "success"
        assert call_count == 3
        # Should have slept twice (after first two failures)
        assert mock_sleep.call_count == 2
        # Check exponential backoff
        calls = mock_sleep.call_args_list
        assert calls[0][0][0] == 0.01  # First retry: base delay
        assert calls[1][0][0] == 0.02  # Second retry: 2x delay
    
    @pytest.mark.asyncio
    async def test_complete_all_models_exhausted(
        self,
        router,
        sample_messages
    ):
        """Test when all models (primary + fallbacks) fail."""
        # Arrange
        mock_client = MagicMock()
        mock_client.complete = AsyncMock(side_effect=ProviderError("All failed"))
        
        with patch.object(router, '_get_client', return_value=mock_client):
            # Act & Assert
            with pytest.raises(ProviderError) as exc_info:
                await router.complete(sample_messages)
            
            assert "All models failed" in str(exc_info.value)
            assert router.stats["failed_calls"] == 1
    
    @pytest.mark.asyncio
    async def test_stream_no_fallback(
        self,
        router,
        mock_router_clients,
        sample_messages
    ):
        """Test that streaming does NOT support fallback."""
        # Arrange
        async def mock_stream():
            yield StreamChunk(
                id="test",
                created=12345,
                model="gpt-4o-mini",
                choices=[{"index": 0, "delta": {"content": "test"}, "finish_reason": None}],
                object="chat.completion.chunk"
            )
        
        mock_router_clients["primary"].stream.return_value = mock_stream()
        
        # Act
        chunks = []
        async for chunk in router.stream(sample_messages):
            chunks.append(chunk)
        
        # Assert
        assert len(chunks) == 1
        # Fallback should not be attempted in streaming
        assert router.stats["fallback_uses"] == 0
    
    def test_get_stats(self, router):
        """Test statistics retrieval."""
        stats = router.get_stats()
        
        assert isinstance(stats, dict)
        assert "total_calls" in stats
        assert "successful_calls" in stats
        assert "failed_calls" in stats
        assert "fallback_uses" in stats
        assert "total_retries" in stats
    
    def test_reset_stats(self, router):
        """Test statistics reset."""
        # Modify stats
        router.stats["total_calls"] = 100
        router.stats["successful_calls"] = 95
        router.stats["failed_calls"] = 5
        
        # Reset
        router.reset_stats()
        
        # Verify all zeroed
        assert router.stats["total_calls"] == 0
        assert router.stats["successful_calls"] == 0
        assert router.stats["failed_calls"] == 0


class TestTokenCountingComprehensive:
    """Comprehensive token counting tests."""
    
    def test_count_tokens_openai_basic(self, patch_tiktoken):
        """Test basic OpenAI token counting."""
        from good_agent.llm_client.tokens import count_tokens_openai
        
        # Arrange
        mock_encoding = patch_tiktoken.encoding_for_model.return_value
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        
        # Act
        count = count_tokens_openai("Hello world", "gpt-4o")
        
        # Assert
        assert count == 5
        patch_tiktoken.encoding_for_model.assert_called_once_with("gpt-4o")
    
    def test_count_tokens_anthropic_approximation(self):
        """Test Anthropic approximation (3.5 chars/token)."""
        from good_agent.llm_client.tokens import count_tokens_anthropic
        
        # 350 chars = ~100 tokens (350 / 3.5)
        text = "x" * 350
        count = count_tokens_anthropic(text)
        
        assert 95 < count < 105  # Allow small variance
    
    def test_count_tokens_auto_detection(self, patch_tiktoken):
        """Test automatic provider detection."""
        from good_agent.llm_client.tokens import count_tokens
        
        mock_encoding = patch_tiktoken.encoding_for_model.return_value
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        
        # OpenAI models
        count = count_tokens("test", "gpt-4o")
        assert count == 5
        
        # Anthropic models (no tiktoken call)
        patch_tiktoken.reset_mock()
        count = count_tokens("x" * 350, "claude-3.5-sonnet")
        assert 95 < count < 105
        patch_tiktoken.encoding_for_model.assert_not_called()
    
    def test_count_message_tokens_basic(self, patch_tiktoken):
        """Test message token counting with overhead."""
        from good_agent.llm_client.tokens import count_message_tokens
        
        mock_encoding = patch_tiktoken.encoding_for_model.return_value
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"}
        ]
        
        total = count_message_tokens(messages, "gpt-4o")
        
        # Should include message overhead (4 per message + 2 final)
        # 2 messages * (4 overhead + 5 role + 5 content) + 2 = 30
        assert total == 30
    
    def test_count_message_tokens_with_tool_calls(self, patch_tiktoken):
        """Test token counting with tool calls."""
        from good_agent.llm_client.tokens import count_message_tokens
        
        mock_encoding = patch_tiktoken.encoding_for_model.return_value
        mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
        
        messages = [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": '{"location": "SF"}'
                        }
                    }
                ]
            }
        ]
        
        total = count_message_tokens(messages, "gpt-4o")
        
        # Should count: role, function name, arguments
        assert total > 0
        # At least 3 encode calls (role, name, arguments)
        assert mock_encoding.encode.call_count >= 3


class TestCostCalculationComprehensive:
    """Comprehensive cost calculation tests."""
    
    def test_calculate_cost_gpt4(self, patch_cost_database):
        """Test cost calculation for GPT-4."""
        from good_agent.llm_client.costs import calculate_cost
        
        cost = calculate_cost(
            model="gpt-4",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        # $0.03 per 1K input + $0.06 per 1K output
        expected = (1000 * 0.00003) + (500 * 0.00006)
        assert abs(cost - expected) < 0.0001
    
    def test_calculate_cost_from_usage(self, patch_cost_database):
        """Test cost calculation from Usage object."""
        from good_agent.llm_client.costs import calculate_cost_from_usage
        
        usage = Usage(
            prompt_tokens=1000,
            completion_tokens=500,
            total_tokens=1500
        )
        
        cost = calculate_cost_from_usage("gpt-4o-mini", usage)
        
        # GPT-4o-mini: $0.00000015 input, $0.0000006 output
        expected = (1000 * 0.00000015) + (500 * 0.0000006)
        assert abs(cost - expected) < 0.0000001
    
    def test_calculate_cost_unknown_model(self, patch_cost_database):
        """Test cost calculation for unknown model returns 0."""
        from good_agent.llm_client.costs import calculate_cost
        
        cost = calculate_cost(
            model="unknown-model-xyz",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        assert cost == 0.0
    
    def test_calculate_cost_model_variant(self, patch_cost_database):
        """Test cost calculation matches model variants."""
        from good_agent.llm_client.costs import calculate_cost
        
        # Should match "gpt-4" in database
        cost = calculate_cost(
            model="gpt-4-0125-preview",
            prompt_tokens=1000,
            completion_tokens=500
        )
        
        assert cost > 0
```

## Key Testing Patterns Demonstrated

### 1. **Fixture Composition**
- Build complex fixtures from simple ones
- Use factory fixtures for flexible test data
- Mock at the right boundary (SDK, not implementation)

### 2. **Async Testing**
- Use `@pytest.mark.asyncio` consistently
- Mock async functions with `AsyncMock`
- Handle async generators properly

### 3. **Error Testing**
- Test each error type
- Verify error messages
- Test error conversion/wrapping

### 4. **Edge Cases**
- Empty inputs
- Missing fields
- Unknown models
- Malformed data

### 5. **Integration Points**
- Mock SDKs, not our implementation
- Test conversion logic thoroughly
- Verify SDK call parameters

### 6. **Performance Patterns**
- Mock expensive operations (tiktoken)
- Use fast delays in tests (0.01s not 1s)
- Test caching behavior

## Running These Tests

```bash
# Run all unit tests
pytest tests/unit/llm_client/ -v

# Run specific test class
pytest tests/unit/llm_client/test_comprehensive.py::TestOpenAIClientComprehensive -v

# Run with coverage
pytest tests/unit/llm_client/ --cov=good_agent.llm_client --cov-report=term-missing

# Run fast (no slow tests)
pytest tests/unit/llm_client/ -v -m "not slow"
```

## Expected Results

```
tests/unit/llm_client/test_comprehensive.py::TestOpenAIClientComprehensive::test_complete_success PASSED
tests/unit/llm_client/test_comprehensive.py::TestOpenAIClientComprehensive::test_complete_with_tool_calling PASSED
tests/unit/llm_client/test_comprehensive.py::TestOpenAIClientComprehensive::test_complete_rate_limit_error PASSED
...
================================ 30 passed in 0.45s ================================
```

All tests should pass in under 1 second.
