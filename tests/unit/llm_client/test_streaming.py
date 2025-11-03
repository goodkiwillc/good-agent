"""
Tests for streaming support.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch


class TestStreaming:
    """Test streaming functionality."""
    
    @pytest.mark.asyncio
    async def test_router_streaming(self):
        """Test router streaming."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        from good_agent.llm_client.types.chat import StreamChunk
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        
        # Mock streaming
        async def mock_stream(*args, **kwargs):
            for i, content in enumerate(["Hello", " ", "world", "!"]):
                yield StreamChunk(
                    id=f"chunk-{i}",
                    model="gpt-4o-mini",
                    choices=[{"delta": {"content": content}, "index": 0}],
                    created=1234567890
                )
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.chat_stream = mock_stream
            mock_get_provider.return_value = mock_provider
            
            chunks = []
            stream_response = await router.acompletion(
                messages=[Message(role="user", content="Test")],
                stream=True
            )
            async for chunk in stream_response:
                chunks.append(chunk)
        
        assert len(chunks) == 4
        assert chunks[0].get_content() == "Hello"
        assert chunks[3].get_content() == "!"
    
    @pytest.mark.asyncio
    async def test_provider_streaming(self):
        """Test OpenAI provider streaming."""
        from good_agent.llm_client.providers.openai import OpenAIProvider
        from good_agent.llm_client.types.common import Message
        
        provider = OpenAIProvider(api_key="test-key")
        
        # Mock OpenAI streaming
        async def mock_stream():
            for i, content in enumerate(["Test", " ", "response"]):
                chunk = Mock()
                chunk.id = f"chunk-{i}"
                chunk.model = "gpt-4o-mini"
                chunk.choices = [Mock(delta=Mock(content=content, role=None if i > 0 else "assistant"), index=0)]
                chunk.created = 1234567890
                chunk.model_dump = Mock(return_value={
                    "id": f"chunk-{i}",
                    "model": "gpt-4o-mini",
                    "choices": [{"delta": {"content": content}, "index": 0}],
                    "created": 1234567890
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
        
        assert len(chunks) == 3
        full_text = "".join(chunk.get_content() or "" for chunk in chunks)
        assert full_text == "Test response"
