"""
Tests for chat capability protocol (RED phase).

Tests that a provider implementing ChatCapability has the right interface.
"""

import pytest
from typing import Protocol, runtime_checkable


class TestChatCapability:
    """Test ChatCapability protocol definition."""
    
    def test_protocol_exists(self):
        """Test that ChatCapability protocol is importable."""
        from good_agent.llm_client.capabilities.chat import ChatCapability
        
        assert ChatCapability is not None
        assert isinstance(ChatCapability, type)
    
    def test_protocol_is_runtime_checkable(self):
        """Test that ChatCapability is runtime checkable."""
        from good_agent.llm_client.capabilities.chat import ChatCapability
        
        # Should be a Protocol
        assert hasattr(ChatCapability, '__protocol_attrs__')
    
    def test_chat_complete_method_required(self):
        """Test that chat_complete method is part of protocol."""
        from good_agent.llm_client.capabilities.chat import ChatCapability
        
        # Protocol should define chat_complete
        assert 'chat_complete' in dir(ChatCapability)
    
    def test_chat_stream_method_required(self):
        """Test that chat_stream method is part of protocol."""
        from good_agent.llm_client.capabilities.chat import ChatCapability
        
        # Protocol should define chat_stream
        assert 'chat_stream' in dir(ChatCapability)
    
    def test_mock_implementation(self):
        """Test that a class implementing the protocol works."""
        from good_agent.llm_client.capabilities.chat import ChatCapability
        from good_agent.llm_client.types.chat import ChatResponse, StreamChunk
        from good_agent.llm_client.types.common import Message, Usage
        from typing import AsyncIterator
        
        class MockChatProvider:
            """Mock provider implementing ChatCapability."""
            
            async def chat_complete(
                self,
                messages: list[Message],
                model: str,
                **kwargs
            ) -> ChatResponse:
                """Mock implementation."""
                return ChatResponse(
                    id="test-123",
                    model=model,
                    choices=[{"message": Message(role="assistant", content="Test")}],
                    usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
                    created=1234567890
                )
            
            async def chat_stream(
                self,
                messages: list[Message],
                model: str,
                **kwargs
            ) -> AsyncIterator[StreamChunk]:
                """Mock implementation."""
                yield StreamChunk(
                    id="test-123",
                    model=model,
                    choices=[{"delta": {"content": "Test"}}],
                    created=1234567890
                )
        
        # Should be able to create instance
        provider = MockChatProvider()
        
        # Should be recognized as implementing the protocol
        assert isinstance(provider, ChatCapability)
    
    @pytest.mark.asyncio
    async def test_mock_implementation_works(self):
        """Test that mock implementation actually works."""
        from good_agent.llm_client.capabilities.chat import ChatCapability
        from good_agent.llm_client.types.common import Message
        
        class MockChatProvider:
            """Mock provider."""
            
            async def chat_complete(self, messages, model, **kwargs):
                from good_agent.llm_client.types.chat import ChatResponse
                from good_agent.llm_client.types.common import Usage
                
                return ChatResponse(
                    id="test",
                    model=model,
                    choices=[{"message": Message(role="assistant", content="Hello")}],
                    usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
                    created=1234567890
                )
            
            async def chat_stream(self, messages, model, **kwargs):
                from good_agent.llm_client.types.chat import StreamChunk
                
                yield StreamChunk(
                    id="test",
                    model=model,
                    choices=[{"delta": {"content": "Hi"}}],
                    created=1234567890
                )
        
        provider = MockChatProvider()
        
        # Test chat_complete
        response = await provider.chat_complete(
            messages=[Message(role="user", content="Test")],
            model="test-model"
        )
        assert response.choices[0]["message"].content == "Hello"
        
        # Test chat_stream
        chunks = []
        async for chunk in provider.chat_stream(
            messages=[Message(role="user", content="Test")],
            model="test-model"
        ):
            chunks.append(chunk)
        
        assert len(chunks) == 1
        assert chunks[0].get_content() == "Hi"
