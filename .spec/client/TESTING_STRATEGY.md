# Testing Strategy for LLM Client

## Overview

Comprehensive testing strategy for the new lightweight LLM client, ensuring high quality, fast execution, and maintainable tests.

## Testing Principles

1. **Fast Unit Tests** - Mock external dependencies, run in <1s
2. **Reliable Integration Tests** - Use VCR.py for deterministic HTTP mocking
3. **Comprehensive Coverage** - Target >90% code coverage
4. **Test Isolation** - Each test is independent, no shared state
5. **Clear Fixtures** - Reusable, well-named fixtures
6. **Performance Tests** - Verify speed targets (<200ms imports)

## Test Structure

```
tests/
├── conftest.py                           # Global fixtures and configuration
├── unit/
│   └── llm_client/
│       ├── conftest.py                  # Unit test fixtures
│       ├── test_types.py                # Type definitions tests
│       ├── test_base.py                 # Base protocol tests
│       ├── test_tokens.py               # Token counting tests
│       ├── test_costs.py                # Cost calculation tests
│       ├── test_exceptions.py           # Exception handling tests
│       ├── providers/
│       │   ├── conftest.py             # Provider fixtures
│       │   ├── test_openai_client.py   # OpenAI provider unit tests
│       │   ├── test_anthropic_client.py # Anthropic provider unit tests
│       │   ├── test_openrouter_client.py # OpenRouter provider unit tests
│       │   └── test_provider_registry.py # Registry tests
│       └── test_router.py               # Router unit tests
├── integration/
│   └── llm_client/
│       ├── conftest.py                  # Integration fixtures
│       ├── test_openai_integration.py   # OpenAI real API tests (VCR)
│       ├── test_anthropic_integration.py # Anthropic real API tests (VCR)
│       ├── test_router_fallback.py      # Fallback logic integration
│       ├── test_streaming.py            # Streaming tests
│       └── test_instructor_compat.py    # Instructor compatibility
└── performance/
    └── llm_client/
        ├── test_import_time.py          # Import speed tests
        ├── test_first_call.py           # Cold start tests
        └── test_throughput.py           # Request throughput tests
```

## Test Categories

### 1. Unit Tests (Fast, Mocked)

**Goal:** Test logic in isolation without external dependencies
**Execution Time:** <1 second total
**Coverage Target:** >95%

#### Type Tests (`test_types.py`)
- Pydantic model validation
- Type conversions
- Serialization/deserialization

#### Base Protocol Tests (`test_base.py`)
- Protocol compliance
- ABC enforcement
- Interface contracts

#### Token Counting Tests (`test_tokens.py`)
- Accurate token counting
- Model-specific tokenizers
- Message token calculation
- Caching behavior

#### Cost Calculation Tests (`test_costs.py`)
- Accurate cost calculation
- Model cost lookup
- Unknown model handling
- Lazy loading of cost database

#### Provider Tests (`test_*_client.py`)
- Response conversion
- Error handling
- Parameter mapping
- Model capability detection
- Mock all HTTP calls

#### Router Tests (`test_router.py`)
- Fallback logic
- Retry behavior
- Model selection
- Statistics tracking
- Client caching

### 2. Integration Tests (VCR.py)

**Goal:** Test real API integration with recorded cassettes
**Execution Time:** <5 seconds (using VCR)
**Coverage Target:** Critical paths

#### Real API Tests
- OpenAI completion
- OpenAI streaming
- Anthropic completion (if used)
- OpenRouter completion
- Tool/function calling
- Error scenarios

#### Router Integration
- Multi-model fallback
- Actual retries
- Cost calculation with real responses
- Token counting validation

### 3. Performance Tests

**Goal:** Verify speed targets
**Execution Time:** <10 seconds
**Coverage Target:** Key metrics

#### Import Speed
- Module import time <200ms
- Lazy loading verification
- Provider import isolation

#### Runtime Performance
- First API call latency
- Subsequent call latency
- Streaming throughput
- Memory usage

## Test Fixtures

### Global Fixtures (in `conftest.py`)

```python
# tests/conftest.py additions

@pytest.fixture
def mock_openai_response():
    """Standard mock OpenAI response."""
    return {
        "id": "chatcmpl-test123",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "Test response"
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "total_tokens": 15
        }
    }


@pytest.fixture
def mock_anthropic_response():
    """Standard mock Anthropic response."""
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": "Test response"}],
        "model": "claude-3.5-sonnet",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 10,
            "output_tokens": 5
        }
    }


@pytest.fixture
def sample_messages():
    """Standard test messages."""
    return [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
```

### Unit Test Fixtures

```python
# tests/unit/llm_client/conftest.py

import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_openai_sdk():
    """Mock OpenAI SDK client."""
    mock = MagicMock()
    mock.chat = MagicMock()
    mock.chat.completions = MagicMock()
    mock.chat.completions.create = AsyncMock()
    return mock


@pytest.fixture
def mock_tiktoken():
    """Mock tiktoken for token counting."""
    mock = MagicMock()
    mock.encode = MagicMock(return_value=[1, 2, 3, 4, 5])  # 5 tokens
    return mock


@pytest.fixture
def openai_client(mock_openai_sdk):
    """OpenAI client with mocked SDK."""
    from good_agent.llm_client.providers.openai import OpenAIClient
    client = OpenAIClient(api_key="test-key")
    client._client = mock_openai_sdk
    return client


@pytest.fixture
def router(openai_client):
    """Router with mocked clients."""
    from good_agent.llm_client.router import ModelRouter
    router = ModelRouter(
        primary_model="gpt-4o-mini",
        fallback_models=["gpt-3.5-turbo"]
    )
    # Inject mocked client
    router._clients["openai"] = openai_client
    return router
```

### Integration Test Fixtures

```python
# tests/integration/llm_client/conftest.py

import pytest
import os


@pytest.fixture
def vcr_config():
    """VCR configuration for LLM client tests."""
    return {
        "filter_headers": [
            "authorization",
            "x-api-key",
        ],
        "filter_post_data_parameters": [
            "api_key",
        ],
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "record_mode": "once",  # Use 'all' to re-record
    }


@pytest.fixture
def real_openai_client():
    """Real OpenAI client for integration tests."""
    from good_agent.llm_client.providers.openai import OpenAIClient
    api_key = os.getenv("OPENAI_API_KEY", "test-key")
    return OpenAIClient(api_key=api_key)


@pytest.fixture
def integration_router():
    """Router for integration tests."""
    from good_agent.llm_client.router import ModelRouter
    return ModelRouter(
        primary_model="gpt-4o-mini",
        fallback_models=["gpt-3.5-turbo"],
        api_key=os.getenv("OPENAI_API_KEY", "test-key")
    )
```

## Example Tests

### Unit Test Example: Token Counting

```python
# tests/unit/llm_client/test_tokens.py

import pytest
from unittest.mock import patch, MagicMock


class TestTokenCounting:
    """Test token counting functionality."""
    
    def test_count_tokens_openai_with_tiktoken(self):
        """Test OpenAI token counting using tiktoken."""
        from good_agent.llm_client.tokens import count_tokens_openai
        
        with patch('good_agent.llm_client.tokens.tiktoken') as mock_tiktoken:
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
            mock_tiktoken.encoding_for_model.return_value = mock_encoding
            
            count = count_tokens_openai("Hello world", "gpt-4o")
            
            assert count == 5
            mock_tiktoken.encoding_for_model.assert_called_once_with("gpt-4o")
            mock_encoding.encode.assert_called_once_with("Hello world")
    
    def test_count_tokens_openai_caching(self):
        """Test that tiktoken encoders are cached."""
        from good_agent.llm_client.tokens import count_tokens_openai, _tiktoken_cache
        
        _tiktoken_cache.clear()  # Start fresh
        
        with patch('good_agent.llm_client.tokens.tiktoken') as mock_tiktoken:
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3]
            mock_tiktoken.encoding_for_model.return_value = mock_encoding
            
            # First call - should cache
            count_tokens_openai("test", "gpt-4o")
            # Second call - should use cache
            count_tokens_openai("test2", "gpt-4o")
            
            # encoding_for_model should only be called once
            assert mock_tiktoken.encoding_for_model.call_count == 1
    
    def test_count_tokens_anthropic_approximation(self):
        """Test Anthropic token approximation."""
        from good_agent.llm_client.tokens import count_tokens_anthropic
        
        text = "Hello world! " * 100  # 1300 chars
        count = count_tokens_anthropic(text)
        
        # Should be approximately 371 tokens (1300 / 3.5)
        assert 350 < count < 400
    
    def test_count_tokens_auto_detection(self):
        """Test automatic provider detection."""
        from good_agent.llm_client.tokens import count_tokens
        
        with patch('good_agent.llm_client.tokens.count_tokens_openai') as mock_openai, \
             patch('good_agent.llm_client.tokens.count_tokens_anthropic') as mock_anthropic:
            
            mock_openai.return_value = 10
            mock_anthropic.return_value = 8
            
            # OpenAI model
            count = count_tokens("test", "gpt-4o")
            assert count == 10
            mock_openai.assert_called_once()
            
            # Anthropic model
            count = count_tokens("test", "claude-3.5-sonnet")
            assert count == 8
            mock_anthropic.assert_called_once()
    
    def test_count_message_tokens(self):
        """Test counting tokens in message list."""
        from good_agent.llm_client.tokens import count_message_tokens
        
        messages = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        
        with patch('good_agent.llm_client.tokens.count_tokens') as mock_count:
            mock_count.return_value = 5  # Each text part returns 5 tokens
            
            total = count_message_tokens(messages, "gpt-4o")
            
            # 3 messages * (4 overhead + 5 role + 5 content) + 2 final = 44
            assert total == 44
    
    def test_count_message_tokens_with_tool_calls(self):
        """Test counting tokens with tool calls."""
        from good_agent.llm_client.tokens import count_message_tokens
        
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
                            "arguments": '{"location": "San Francisco"}'
                        }
                    }
                ]
            }
        ]
        
        with patch('good_agent.llm_client.tokens.count_tokens') as mock_count:
            mock_count.return_value = 5
            
            total = count_message_tokens(messages, "gpt-4o")
            
            # Should count function name and arguments
            assert total > 0
            assert mock_count.call_count >= 3  # role, name, arguments
```

### Unit Test Example: Router Fallback

```python
# tests/unit/llm_client/test_router.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from good_agent.llm_client.exceptions import RateLimitError, ProviderError


class TestModelRouter:
    """Test router fallback and retry logic."""
    
    @pytest.mark.asyncio
    async def test_complete_success_first_try(self, router, openai_client, mock_openai_response):
        """Test successful completion on first try."""
        from good_agent.llm_client.types import ModelResponse
        
        # Mock successful response
        expected = ModelResponse(**mock_openai_response)
        openai_client._client.chat.completions.create.return_value = expected
        
        messages = [{"role": "user", "content": "Hello"}]
        response = await router.complete(messages)
        
        assert response.id == "chatcmpl-test123"
        assert response.choices[0].message.content == "Test response"
        assert router.stats["successful_calls"] == 1
        assert router.stats["fallback_uses"] == 0
    
    @pytest.mark.asyncio
    async def test_complete_fallback_on_rate_limit(self, router, sample_messages):
        """Test fallback to secondary model on rate limit."""
        from good_agent.llm_client.types import ModelResponse
        
        # First model: rate limit
        # Second model: success
        mock_client = MagicMock()
        mock_client.complete = AsyncMock()
        
        # First call fails with rate limit
        mock_client.complete.side_effect = [
            RateLimitError("Rate limited"),
            ModelResponse(
                id="chatcmpl-fallback",
                created=12345,
                model="gpt-3.5-turbo",
                choices=[],
                object="chat.completion"
            )
        ]
        
        # Inject mock client
        router._clients = {"openai": mock_client}
        
        response = await router.complete(sample_messages)
        
        assert response.id == "chatcmpl-fallback"
        assert router.stats["fallback_uses"] == 1
        assert mock_client.complete.call_count == 2
    
    @pytest.mark.asyncio
    async def test_complete_retry_with_exponential_backoff(self, router, sample_messages):
        """Test retry with exponential backoff."""
        import asyncio
        from good_agent.llm_client.types import ModelResponse
        
        mock_client = MagicMock()
        mock_client.complete = AsyncMock()
        
        # Fail twice, succeed third time
        mock_client.complete.side_effect = [
            RateLimitError("Rate limited"),
            RateLimitError("Rate limited"),
            ModelResponse(
                id="chatcmpl-success",
                created=12345,
                model="gpt-4o-mini",
                choices=[],
                object="chat.completion"
            )
        ]
        
        router._clients = {"openai": mock_client}
        router.max_retries_per_model = 3
        router.retry_delay = 0.01  # Fast for testing
        
        with patch('asyncio.sleep') as mock_sleep:
            response = await router.complete(sample_messages)
        
        assert response.id == "chatcmpl-success"
        assert mock_client.complete.call_count == 3
        # Should have slept twice (after first two failures)
        assert mock_sleep.call_count == 2
    
    @pytest.mark.asyncio
    async def test_complete_all_models_fail(self, router, sample_messages):
        """Test behavior when all models fail."""
        mock_client = MagicMock()
        mock_client.complete = AsyncMock()
        mock_client.complete.side_effect = ProviderError("API Error")
        
        router._clients = {"openai": mock_client}
        
        with pytest.raises(ProviderError) as exc_info:
            await router.complete(sample_messages)
        
        assert "All models failed" in str(exc_info.value)
        assert router.stats["failed_calls"] == 1
    
    def test_get_stats(self, router):
        """Test statistics retrieval."""
        stats = router.get_stats()
        
        assert "total_calls" in stats
        assert "successful_calls" in stats
        assert "failed_calls" in stats
        assert "fallback_uses" in stats
        assert "total_retries" in stats
    
    def test_reset_stats(self, router):
        """Test statistics reset."""
        router.stats["total_calls"] = 10
        router.stats["successful_calls"] = 8
        
        router.reset_stats()
        
        assert router.stats["total_calls"] == 0
        assert router.stats["successful_calls"] == 0
```

### Unit Test Example: OpenAI Client

```python
# tests/unit/llm_client/providers/test_openai_client.py

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from openai import OpenAIError


class TestOpenAIClient:
    """Test OpenAI provider client."""
    
    @pytest.mark.asyncio
    async def test_complete_basic(self, openai_client, sample_messages, mock_openai_response):
        """Test basic completion."""
        from good_agent.llm_client.types import ModelResponse
        
        # Mock SDK response
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-test123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4o-mini"
        mock_response.choices = [MagicMock(
            index=0,
            message=MagicMock(
                role="assistant",
                content="Test response",
                tool_calls=None
            ),
            finish_reason="stop"
        )]
        mock_response.usage = MagicMock(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15
        )
        mock_response.system_fingerprint = "fp_test"
        
        openai_client._client.chat.completions.create.return_value = mock_response
        
        response = await openai_client.complete(
            messages=sample_messages,
            model="gpt-4o-mini"
        )
        
        assert isinstance(response, ModelResponse)
        assert response.id == "chatcmpl-test123"
        assert response.choices[0].message.content == "Test response"
        assert response.usage.total_tokens == 15
    
    @pytest.mark.asyncio
    async def test_complete_with_tool_calls(self, openai_client, sample_messages):
        """Test completion with tool/function calls."""
        # Mock response with tool calls
        mock_response = MagicMock()
        mock_response.id = "chatcmpl-tool123"
        mock_response.created = 1234567890
        mock_response.model = "gpt-4o-mini"
        
        tool_call = MagicMock()
        tool_call.id = "call_abc123"
        tool_call.type = "function"
        tool_call.function = MagicMock(
            name="get_weather",
            arguments='{"location": "SF"}'
        )
        
        mock_response.choices = [MagicMock(
            index=0,
            message=MagicMock(
                role="assistant",
                content="",
                tool_calls=[tool_call]
            ),
            finish_reason="tool_calls"
        )]
        mock_response.usage = MagicMock(
            prompt_tokens=20,
            completion_tokens=10,
            total_tokens=30
        )
        
        openai_client._client.chat.completions.create.return_value = mock_response
        
        response = await openai_client.complete(
            messages=sample_messages,
            model="gpt-4o-mini",
            tools=[{"type": "function", "function": {"name": "get_weather"}}]
        )
        
        assert len(response.choices[0].message.tool_calls) == 1
        assert response.choices[0].message.tool_calls[0]["id"] == "call_abc123"
        assert response.choices[0].message.tool_calls[0]["function"]["name"] == "get_weather"
    
    @pytest.mark.asyncio
    async def test_complete_error_handling(self, openai_client, sample_messages):
        """Test error conversion."""
        from good_agent.llm_client.exceptions import RateLimitError
        
        # Mock rate limit error
        openai_client._client.chat.completions.create.side_effect = \
            OpenAIError("rate_limit exceeded")
        
        with pytest.raises(RateLimitError):
            await openai_client.complete(
                messages=sample_messages,
                model="gpt-4o-mini"
            )
    
    @pytest.mark.asyncio
    async def test_stream_basic(self, openai_client, sample_messages):
        """Test streaming completion."""
        from good_agent.llm_client.types import StreamChunk
        
        # Mock streaming response
        async def mock_stream():
            chunks = [
                MagicMock(
                    id="chatcmpl-stream1",
                    created=12345,
                    model="gpt-4o-mini",
                    choices=[MagicMock(
                        index=0,
                        delta=MagicMock(role="assistant", content="Hello", tool_calls=None),
                        finish_reason=None
                    )]
                ),
                MagicMock(
                    id="chatcmpl-stream1",
                    created=12345,
                    model="gpt-4o-mini",
                    choices=[MagicMock(
                        index=0,
                        delta=MagicMock(role=None, content=" world", tool_calls=None),
                        finish_reason=None
                    )]
                ),
                MagicMock(
                    id="chatcmpl-stream1",
                    created=12345,
                    model="gpt-4o-mini",
                    choices=[MagicMock(
                        index=0,
                        delta=MagicMock(role=None, content=None, tool_calls=None),
                        finish_reason="stop"
                    )]
                ),
            ]
            for chunk in chunks:
                yield chunk
        
        openai_client._client.chat.completions.create.return_value = mock_stream()
        
        chunks = []
        async for chunk in openai_client.stream(
            messages=sample_messages,
            model="gpt-4o-mini"
        ):
            assert isinstance(chunk, StreamChunk)
            chunks.append(chunk)
        
        assert len(chunks) == 3
        assert chunks[0].content == "Hello"
        assert chunks[1].content == " world"
        assert chunks[2].finish_reason == "stop"
    
    def test_supports_streaming(self, openai_client):
        """Test streaming support detection."""
        assert openai_client.supports_streaming("gpt-4o-mini") is True
        assert openai_client.supports_streaming("gpt-4") is True
        assert openai_client.supports_streaming("o1-preview") is False
    
    def test_supports_tools(self, openai_client):
        """Test tool calling support detection."""
        assert openai_client.supports_tools("gpt-4o-mini") is True
        assert openai_client.supports_tools("gpt-4") is True
        assert openai_client.supports_tools("gpt-3.5-turbo") is True
    
    def test_count_tokens_with_tiktoken(self, openai_client):
        """Test token counting."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_encoding = MagicMock()
            mock_encoding.encode.return_value = [1, 2, 3, 4, 5]
            mock_tiktoken.return_value = mock_encoding
            
            count = openai_client.count_tokens("Hello world", "gpt-4o-mini")
            
            assert count == 5
    
    def test_count_tokens_fallback_on_unknown_model(self, openai_client):
        """Test token counting fallback for unknown models."""
        with patch('tiktoken.encoding_for_model') as mock_tiktoken:
            mock_tiktoken.side_effect = KeyError("Unknown model")
            
            with patch('tiktoken.get_encoding') as mock_get_encoding:
                mock_encoding = MagicMock()
                mock_encoding.encode.return_value = [1, 2, 3]
                mock_get_encoding.return_value = mock_encoding
                
                count = openai_client.count_tokens("test", "custom-model")
                
                assert count == 3
                mock_get_encoding.assert_called_once_with("cl100k_base")
```

### Integration Test Example (with VCR)

```python
# tests/integration/llm_client/test_openai_integration.py

import pytest
import vcr


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_openai_real_completion(real_openai_client):
    """Test real OpenAI API completion (recorded with VCR)."""
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'test successful' and nothing else."}
    ]
    
    response = await real_openai_client.complete(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=10
    )
    
    assert response.id is not None
    assert response.model == "gpt-4o-mini"
    assert len(response.choices) > 0
    assert "test" in response.choices[0].message.content.lower()
    assert response.usage.total_tokens > 0


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_openai_streaming(real_openai_client):
    """Test real OpenAI streaming (recorded with VCR)."""
    messages = [
        {"role": "user", "content": "Count from 1 to 3, one number per line."}
    ]
    
    chunks = []
    async for chunk in real_openai_client.stream(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=50
    ):
        chunks.append(chunk)
    
    assert len(chunks) > 0
    # Last chunk should have finish_reason
    assert chunks[-1].finish_reason is not None
    
    # Combine content
    full_content = "".join(c.content for c in chunks if c.content)
    assert "1" in full_content
    assert "2" in full_content
    assert "3" in full_content


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_openai_function_calling(real_openai_client):
    """Test real OpenAI function calling (recorded with VCR)."""
    messages = [
        {"role": "user", "content": "What's the weather in San Francisco?"}
    ]
    
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a location",
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
    
    response = await real_openai_client.complete(
        messages=messages,
        model="gpt-4o-mini",
        tools=tools,
        tool_choice="auto"
    )
    
    assert len(response.choices) > 0
    choice = response.choices[0]
    
    # Should have tool calls
    assert choice.message.tool_calls is not None
    assert len(choice.message.tool_calls) > 0
    
    tool_call = choice.message.tool_calls[0]
    assert tool_call["function"]["name"] == "get_weather"
    assert "location" in tool_call["function"]["arguments"]


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_router_fallback_integration(integration_router):
    """Test router fallback with real APIs (recorded with VCR)."""
    messages = [{"role": "user", "content": "Hello"}]
    
    # This will use primary model
    response = await integration_router.complete(
        messages=messages,
        max_tokens=10
    )
    
    assert response.choices[0].message.content is not None
    assert integration_router.stats["successful_calls"] == 1


@pytest.mark.vcr()
@pytest.mark.asyncio
async def test_token_counting_accuracy(real_openai_client):
    """Test token counting accuracy against real API."""
    from good_agent.llm_client.tokens import count_message_tokens
    
    messages = [
        {"role": "user", "content": "Hello world! How are you today?"}
    ]
    
    # Get actual token count from API
    response = await real_openai_client.complete(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=5
    )
    
    actual_prompt_tokens = response.usage.prompt_tokens
    
    # Compare with our counter
    estimated_tokens = count_message_tokens(messages, "gpt-4o-mini")
    
    # Should be within 10% accuracy
    accuracy = abs(estimated_tokens - actual_prompt_tokens) / actual_prompt_tokens
    assert accuracy < 0.10, f"Token count off by {accuracy*100:.1f}%"
```

### Performance Test Example

```python
# tests/performance/llm_client/test_import_time.py

import time
import subprocess
import sys


def test_import_time_under_200ms():
    """Test that module import is under 200ms."""
    code = """
import time
start = time.time()
from good_agent.llm_client import ModelRouter, ModelResponse
elapsed = time.time() - start
print(f"{elapsed:.6f}")
"""
    
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True
    )
    
    elapsed = float(result.stdout.strip())
    
    assert elapsed < 0.200, f"Import too slow: {elapsed:.3f}s"
    print(f"✓ Import time: {elapsed:.3f}s")


def test_lazy_loading_providers():
    """Test that providers are not imported until used."""
    code = """
import sys
from good_agent.llm_client import ModelRouter

# Check that provider modules are not yet imported
providers_imported = [
    name for name in sys.modules 
    if 'llm_client.providers.openai' in name
]

print(len(providers_imported))
"""
    
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True
    )
    
    count = int(result.stdout.strip())
    assert count == 0, "Providers should not be imported until used"


def test_tiktoken_not_imported_initially():
    """Test that tiktoken is not imported until token counting is used."""
    code = """
import sys
from good_agent.llm_client import ModelRouter

tiktoken_imported = 'tiktoken' in sys.modules
print(tiktoken_imported)
"""
    
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True
    )
    
    imported = result.stdout.strip() == "True"
    assert not imported, "tiktoken should not be imported until token counting is used"


# tests/performance/llm_client/test_first_call.py

import pytest
import time


@pytest.mark.asyncio
async def test_first_call_latency(real_openai_client):
    """Test latency of first API call."""
    messages = [{"role": "user", "content": "Hi"}]
    
    start = time.time()
    response = await real_openai_client.complete(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=5
    )
    elapsed = time.time() - start
    
    # First call should be under 3 seconds (includes network)
    assert elapsed < 3.0, f"First call too slow: {elapsed:.3f}s"
    print(f"✓ First call latency: {elapsed:.3f}s")
    assert response.choices[0].message.content is not None


@pytest.mark.asyncio
async def test_subsequent_call_latency(real_openai_client):
    """Test that subsequent calls are fast (connection reuse)."""
    messages = [{"role": "user", "content": "Hi"}]
    
    # Warm up
    await real_openai_client.complete(messages=messages, model="gpt-4o-mini", max_tokens=5)
    
    # Measure second call
    start = time.time()
    response = await real_openai_client.complete(
        messages=messages,
        model="gpt-4o-mini",
        max_tokens=5
    )
    elapsed = time.time() - start
    
    # Should be faster than first call
    assert elapsed < 2.0, f"Subsequent call too slow: {elapsed:.3f}s"
    print(f"✓ Subsequent call latency: {elapsed:.3f}s")
```

## Test Execution

### Run All Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/good_agent/llm_client --cov-report=html --cov-report=term

# Run only unit tests (fast)
pytest tests/unit/llm_client/ -v

# Run only integration tests
pytest tests/integration/llm_client/ -v

# Run performance tests
pytest tests/performance/llm_client/ -v
```

### Run Specific Test Categories

```bash
# Fast tests only (unit tests)
pytest tests/unit/ -v -m "not slow"

# Integration tests with VCR
pytest tests/integration/ -v --vcr-record=none

# Re-record VCR cassettes
pytest tests/integration/llm_client/ --vcr-record=all
```

### Continuous Integration

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'
      
      - name: Install dependencies
        run: |
          pip install uv
          uv sync
      
      - name: Run unit tests
        run: pytest tests/unit/ -v --cov=src/good_agent/llm_client
      
      - name: Run integration tests (VCR)
        run: pytest tests/integration/ -v --vcr-record=none
      
      - name: Run performance tests
        run: pytest tests/performance/ -v
      
      - name: Check import time
        run: |
          python -c "import time; start=time.time(); from good_agent.llm_client import ModelRouter; assert time.time()-start < 0.2"
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

## Coverage Goals

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Core types | >95% | Critical |
| Base protocol | >90% | Critical |
| OpenAI client | >90% | High |
| Router | >90% | High |
| Token counting | >85% | High |
| Cost calculation | >85% | Medium |
| Anthropic client | >85% | Medium |
| Error handling | >80% | Medium |

## Test Maintenance

### Updating VCR Cassettes

When API responses change:

```bash
# Re-record all cassettes
pytest tests/integration/ --vcr-record=all

# Re-record specific test
pytest tests/integration/llm_client/test_openai_integration.py::test_openai_real_completion --vcr-record=all
```

### Adding New Tests

1. **Unit Test**: Mock all external dependencies
2. **Integration Test**: Use VCR to record real API calls
3. **Performance Test**: Measure and assert on timing
4. **Add to CI**: Ensure new tests run in CI pipeline

### Test Naming Convention

- `test_<function>_<scenario>`: Descriptive test names
- `test_<class>_<method>_<condition>`: For class tests
- `test_integration_<feature>`: For integration tests
- `test_performance_<metric>`: For performance tests

## Success Criteria

- ✅ Unit test suite runs in <1 second
- ✅ Integration test suite runs in <10 seconds (with VCR)
- ✅ >90% code coverage on critical paths
- ✅ All edge cases tested
- ✅ Performance benchmarks passing
- ✅ CI/CD pipeline green
- ✅ No flaky tests
- ✅ Clear, maintainable test code
