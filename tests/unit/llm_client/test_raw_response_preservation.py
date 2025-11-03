"""
Tests for raw response preservation (RED phase).

Ensures we never lose data from provider responses, even if they add new fields.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch


class TestRawResponsePreservation:
    """Test that we preserve raw provider responses."""
    
    def test_chat_response_has_raw_response_field(self):
        """Test that ChatResponse can store raw response."""
        from good_agent.llm_client.types.chat import ChatResponse
        from good_agent.llm_client.types.common import Usage
        
        # Create a response with raw_response
        response = ChatResponse(
            id="test-123",
            model="gpt-4o-mini",
            choices=[],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            created=1234567890,
            raw_response={"some": "data", "new_field": "value"}
        )
        
        assert response.raw_response is not None
        assert response.raw_response["some"] == "data"
        assert response.raw_response["new_field"] == "value"
    
    def test_stream_chunk_has_raw_response_field(self):
        """Test that StreamChunk can store raw response."""
        from good_agent.llm_client.types.chat import StreamChunk
        
        chunk = StreamChunk(
            id="test-123",
            model="gpt-4o-mini",
            choices=[],
            created=1234567890,
            raw_response={"original": "chunk", "unknown_field": 123}
        )
        
        assert chunk.raw_response is not None
        assert chunk.raw_response["original"] == "chunk"
        assert chunk.raw_response["unknown_field"] == 123
    
    def test_response_accepts_extra_fields(self):
        """Test that responses accept unknown fields via extra='allow'."""
        from good_agent.llm_client.types.chat import ChatResponse
        from good_agent.llm_client.types.common import Usage
        
        # Create response with unknown fields
        response = ChatResponse(
            id="test-123",
            model="gpt-4o-mini",
            choices=[],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            created=1234567890,
            new_provider_field="some_value",  # Unknown field
            experimental_feature={"enabled": True}  # Another unknown field
        )
        
        # Should be accessible via model_extra or direct attribute
        assert hasattr(response, 'new_provider_field') or 'new_provider_field' in response.model_extra
    
    @pytest.mark.asyncio
    async def test_openai_provider_preserves_raw_response(self):
        """Test that OpenAI provider stores the raw response."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock response with extra fields that we don't currently handle
        mock_choice = Mock()
        mock_choice.message.role = "assistant"
        mock_choice.message.content = "Test response"
        mock_choice.message.tool_calls = None
        
        mock_response = Mock()
        mock_response.id = "chatcmpl-123"
        mock_response.model = "gpt-4o-mini"
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.usage.prompt_tokens_details = None
        mock_response.usage.completion_tokens_details = None
        mock_response.created = 1234567890
        mock_response.system_fingerprint = "fp_123"
        
        # Add new fields that might be added by OpenAI in future
        mock_response.new_experimental_field = "future_feature"
        mock_response.metadata = {"custom": "data"}
        
        # Mock the model_dump method to return a dict with all fields
        mock_response.model_dump = Mock(return_value={
            "id": "chatcmpl-123",
            "model": "gpt-4o-mini",
            "choices": [{"message": {"role": "assistant", "content": "Test response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "created": 1234567890,
            "system_fingerprint": "fp_123",
            "new_experimental_field": "future_feature",
            "metadata": {"custom": "data"}
        })
        
        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            response = await provider.chat_complete(
                messages=[Message(role="user", content="Test")],
                model="gpt-4o-mini"
            )
        
        # Verify raw response is preserved
        assert response.raw_response is not None
        assert response.raw_response["new_experimental_field"] == "future_feature"
        assert response.raw_response["metadata"]["custom"] == "data"
    
    @pytest.mark.asyncio
    async def test_openai_stream_preserves_raw_chunks(self):
        """Test that streaming preserves raw chunk data."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock streaming with extra fields
        async def mock_stream():
            chunk = Mock(
                id="chatcmpl-789",
                model="gpt-4o-mini",
                choices=[Mock(delta=Mock(content="Test", role="assistant"), index=0)],
                created=1234567890,
                new_streaming_field="experimental"
            )
            chunk.model_dump = Mock(return_value={
                "id": "chatcmpl-789",
                "model": "gpt-4o-mini",
                "choices": [{"delta": {"content": "Test", "role": "assistant"}, "index": 0}],
                "created": 1234567890,
                "new_streaming_field": "experimental"
            })
            yield chunk
        
        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_stream())
            
            chunks = []
            async for chunk in provider.chat_stream(
                messages=[Message(role="user", content="Test")],
                model="gpt-4o-mini"
            ):
                chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].raw_response is not None
        assert chunks[0].raw_response["new_streaming_field"] == "experimental"
    
    def test_usage_preserves_unknown_token_details(self):
        """Test that Usage preserves unknown token detail fields."""
        from good_agent.llm_client.types.common import Usage
        
        # Create usage with future fields
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            prompt_tokens_details={
                "cached_tokens": 20,
                "new_cache_type": 5  # Future field
            },
            completion_tokens_details={
                "reasoning_tokens": 10,
                "new_token_type": 3  # Future field
            },
            # Future top-level field
            experimental_cost_data={"estimate": 0.001}
        )
        
        # Should preserve all fields
        assert usage.prompt_tokens_details["new_cache_type"] == 5
        assert usage.completion_tokens_details["new_token_type"] == 3
        # Extra field should be accessible
        assert hasattr(usage, 'experimental_cost_data') or 'experimental_cost_data' in usage.model_extra
    
    def test_message_preserves_unknown_fields(self):
        """Test that Message preserves unknown fields."""
        from good_agent.llm_client.types.common import Message
        
        # Create message with future fields
        msg = Message(
            role="assistant",
            content="Test",
            future_metadata={"type": "enhanced"},  # Future field
            experimental_flag=True  # Future field
        )
        
        # Should be accessible
        assert hasattr(msg, 'future_metadata') or 'future_metadata' in msg.model_extra
        assert hasattr(msg, 'experimental_flag') or 'experimental_flag' in msg.model_extra
    
    @pytest.mark.asyncio
    async def test_provider_handles_completely_new_response_structure(self):
        """Test that provider gracefully handles major API changes."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock response with radically different structure
        mock_choice = Mock()
        mock_choice.message.role = "assistant"
        mock_choice.message.content = "Test"
        mock_choice.message.tool_calls = None
        
        mock_response = Mock()
        mock_response.id = "chatcmpl-999"
        mock_response.model = "gpt-5"  # Future model
        mock_response.choices = [mock_choice]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.usage.prompt_tokens_details = None
        mock_response.usage.completion_tokens_details = None
        mock_response.created = 1234567890
        mock_response.system_fingerprint = None
        
        # Add completely new top-level structures
        mock_response.model_dump = Mock(return_value={
            "id": "chatcmpl-999",
            "model": "gpt-5",
            "choices": [{"message": {"role": "assistant", "content": "Test"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "created": 1234567890,
            "new_api_version": "2.0",
            "performance_metrics": {"latency_ms": 150, "tokens_per_second": 100},
            "safety_scores": {"harmful": 0.01, "safe": 0.99}
        })
        
        with patch.object(provider, '_client') as mock_client:
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            
            response = await provider.chat_complete(
                messages=[Message(role="user", content="Test")],
                model="gpt-5"
            )
        
        # Should work and preserve all new data
        assert response.id == "chatcmpl-999"
        assert response.raw_response is not None
        assert response.raw_response["new_api_version"] == "2.0"
        assert response.raw_response["performance_metrics"]["latency_ms"] == 150
        assert response.raw_response["safety_scores"]["harmful"] == 0.01
