"""
Tests for OpenAI provider (RED phase).

These tests use mocks to avoid actual API calls.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import AsyncIterator


class TestOpenAIProvider:
    """Test OpenAI provider implementation."""
    
    def test_provider_creation(self):
        """Test creating an OpenAI provider instance."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        
        provider = OpenAIProvider(api_key="test-key")
        
        assert provider.api_key == "test-key"
        assert provider.provider_name == "openai"
    
    def test_provider_implements_chat_capability(self):
        """Test that OpenAI provider implements ChatCapability."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.capabilities.chat import ChatCapability
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Should implement ChatCapability protocol
        assert isinstance(provider, ChatCapability)
        assert hasattr(provider, 'chat_complete')
        assert hasattr(provider, 'chat_stream')
    
    @pytest.mark.asyncio
    async def test_chat_complete_basic(self):
        """Test basic chat completion."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        # Create provider
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock the OpenAI SDK
        mock_choice = Mock()
        mock_choice.message.role = "assistant"
        mock_choice.message.content = "Hello! How can I help you?"
        mock_choice.message.tool_calls = None
        
        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.model = "gpt-4o-mini"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 8
        mock_response.usage.total_tokens = 18
        mock_response.usage.prompt_tokens_details = None
        mock_response.usage.completion_tokens_details = None
        mock_response.created = 1234567890
        mock_response.system_fingerprint = "fp_123"
        
        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            # Call chat_complete
            response = await provider.chat_complete(
                messages=[Message(role="user", content="Hello")],
                model="gpt-4o-mini"
            )
        
        # Verify response
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4o-mini"
        assert len(response.choices) == 1
        assert response.choices[0]["message"].content == "Hello! How can I help you?"
        assert response.usage.total_tokens == 18
    
    @pytest.mark.asyncio
    async def test_chat_complete_with_tools(self):
        """Test chat completion with tool calls."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock tool call response
        mock_tool_call = Mock()
        mock_tool_call.id = "call_abc123"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = '{"city": "San Francisco"}'
        
        mock_choice = Mock()
        mock_choice.message.role = "assistant"
        mock_choice.message.content = None
        mock_choice.message.tool_calls = [mock_tool_call]
        
        mock_response = Mock()
        mock_response.id = "chatcmpl-456"
        mock_response.model = "gpt-4o-mini"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 50
        mock_response.usage.completion_tokens = 20
        mock_response.usage.total_tokens = 70
        mock_response.usage.prompt_tokens_details = None
        mock_response.usage.completion_tokens_details = None
        mock_response.created = 1234567890
        mock_response.system_fingerprint = "fp_456"
        
        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            response = await provider.chat_complete(
                messages=[Message(role="user", content="What's the weather in SF?")],
                model="gpt-4o-mini",
                tools=[{"type": "function", "function": {"name": "get_weather"}}]
            )
        
        # Verify tool call in response
        assert len(response.choices) == 1
        message = response.choices[0]["message"]
        assert message.tool_calls is not None
        assert len(message.tool_calls) == 1
        assert message.tool_calls[0]["id"] == "call_abc123"
        assert message.tool_calls[0]["function"]["name"] == "get_weather"
    
    @pytest.mark.asyncio
    async def test_chat_stream(self):
        """Test streaming chat completion."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock streaming chunks
        async def mock_stream():
            chunks = [
                Mock(
                    id="chatcmpl-789",
                    model="gpt-4o-mini",
                    choices=[Mock(delta=Mock(content="Hello", role="assistant"), index=0)],
                    created=1234567890
                ),
                Mock(
                    id="chatcmpl-789",
                    model="gpt-4o-mini",
                    choices=[Mock(delta=Mock(content=" there", role=None), index=0)],
                    created=1234567890
                ),
                Mock(
                    id="chatcmpl-789",
                    model="gpt-4o-mini",
                    choices=[Mock(delta=Mock(content="!", role=None), index=0)],
                    created=1234567890
                ),
            ]
            for chunk in chunks:
                yield chunk
        
        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            
            # Collect stream chunks
            chunks = []
            async for chunk in provider.chat_stream(
                messages=[Message(role="user", content="Hi")],
                model="gpt-4o-mini"
            ):
                chunks.append(chunk)
        
        # Verify chunks
        assert len(chunks) == 3
        assert chunks[0].get_content() == "Hello"
        assert chunks[1].get_content() == " there"
        assert chunks[2].get_content() == "!"
    
    @pytest.mark.asyncio
    async def test_chat_complete_with_temperature(self):
        """Test chat completion with custom parameters."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        mock_choice = Mock()
        mock_choice.message.role = "assistant"
        mock_choice.message.content = "Response"
        mock_choice.message.tool_calls = None
        
        mock_response = Mock()
        mock_response.id = "chatcmpl-999"
        mock_response.model = "gpt-4o-mini"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 5
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 10
        mock_response.usage.prompt_tokens_details = None
        mock_response.usage.completion_tokens_details = None
        mock_response.created = 1234567890
        mock_response.system_fingerprint = None
        
        with patch.object(provider, '_client') as mock_client:
            mock_create = AsyncMock(return_value=mock_response)
            mock_client.chat.completions.create = mock_create
            
            await provider.chat_complete(
                messages=[Message(role="user", content="Test")],
                model="gpt-4o-mini",
                temperature=0.7,
                max_tokens=100
            )
            
            # Verify parameters were passed
            call_kwargs = mock_create.call_args.kwargs
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["max_tokens"] == 100
            assert call_kwargs["model"] == "gpt-4o-mini"
