"""
Tests for Router with fallback logic (RED phase).

Tests router functionality including hooks for easy mocking.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Any


class TestRouter:
    """Test Router implementation."""
    
    def test_router_creation(self):
        """Test creating a router with models."""
        from good_agent.llm_client.router import Router
        
        router = Router(
            models=["gpt-4o-mini", "gpt-3.5-turbo"],
            api_key="test-key"
        )
        
        assert router is not None
        assert len(router.models) == 2
    
    def test_router_with_fallback_models(self):
        """Test router with primary and fallback models."""
        from good_agent.llm_client.router import Router
        
        router = Router(
            models=["gpt-4o-mini"],
            fallback_models=["gpt-3.5-turbo", "gpt-4"],
            api_key="test-key"
        )
        
        assert router.models == ["gpt-4o-mini"]
        assert router.fallback_models == ["gpt-3.5-turbo", "gpt-4"]
    
    @pytest.mark.asyncio
    async def test_router_completion_success(self):
        """Test successful completion through router."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        
        # Mock the provider
        mock_response = Mock()
        mock_response.id = "test-123"
        mock_response.model = "gpt-4o-mini"
        mock_response.choices = [{"message": Message(role="assistant", content="Test")}]
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        mock_response.usage.total_tokens = 15
        mock_response.created = 1234567890
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_provider.chat_complete = AsyncMock(return_value=mock_response)
            mock_get_provider.return_value = mock_provider
            
            response = await router.acompletion(
                messages=[Message(role="user", content="Test")]
            )
        
        assert response.id == "test-123"
        assert response.model == "gpt-4o-mini"
    
    @pytest.mark.asyncio
    async def test_router_fallback_on_error(self):
        """Test that router falls back to next model on error."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        
        router = Router(
            models=["gpt-4o-mini"],
            fallback_models=["gpt-3.5-turbo"],
            api_key="test-key"
        )
        
        call_count = 0
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            
            async def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    # First call fails
                    raise Exception("API Error")
                else:
                    # Second call succeeds
                    mock_response = Mock()
                    mock_response.id = "fallback-123"
                    mock_response.model = "gpt-3.5-turbo"
                    mock_response.choices = [{"message": Message(role="assistant", content="Fallback")}]
                    mock_response.usage.prompt_tokens = 10
                    mock_response.usage.completion_tokens = 5
                    mock_response.usage.total_tokens = 15
                    mock_response.created = 1234567890
                    return mock_response
            
            mock_provider.chat_complete = AsyncMock(side_effect=side_effect)
            mock_get_provider.return_value = mock_provider
            
            response = await router.acompletion(
                messages=[Message(role="user", content="Test")]
            )
        
        # Should have tried both models
        assert call_count == 2
        assert response.model == "gpt-3.5-turbo"
        assert response.choices[0]["message"].content == "Fallback"
    
    @pytest.mark.asyncio
    async def test_router_retries_before_fallback(self):
        """Test that router retries before falling back."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        
        router = Router(
            models=["gpt-4o-mini"],
            fallback_models=["gpt-3.5-turbo"],
            api_key="test-key",
            max_retries=2
        )
        
        call_count = 0
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            
            async def side_effect(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count <= 2:
                    # First 2 calls fail (initial + 1 retry)
                    raise Exception("API Error")
                else:
                    # Fallback succeeds
                    mock_response = Mock()
                    mock_response.id = "success"
                    mock_response.model = "gpt-3.5-turbo"
                    mock_response.choices = [{"message": Message(role="assistant", content="OK")}]
                    mock_response.usage.prompt_tokens = 10
                    mock_response.usage.completion_tokens = 5
                    mock_response.usage.total_tokens = 15
                    mock_response.created = 1234567890
                    return mock_response
            
            mock_provider.chat_complete = AsyncMock(side_effect=side_effect)
            mock_get_provider.return_value = mock_provider
            
            response = await router.acompletion(
                messages=[Message(role="user", content="Test")]
            )
        
        # Should have called 3 times: 2 retries on primary, then fallback
        assert call_count == 3


class TestRouterHooks:
    """Test router hooks for monitoring and testing."""
    
    @pytest.mark.asyncio
    async def test_before_request_hook(self):
        """Test before_request hook is called."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        
        hook_called = False
        hook_data = {}
        
        def before_hook(model: str, messages: list[Message], **kwargs):
            nonlocal hook_called, hook_data
            hook_called = True
            hook_data = {"model": model, "messages": messages, "kwargs": kwargs}
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        router.add_hook("before_request", before_hook)
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_response = Mock()
            mock_response.id = "test"
            mock_response.model = "gpt-4o-mini"
            mock_response.choices = [{"message": Message(role="assistant", content="Hi")}]
            mock_response.usage.prompt_tokens = 5
            mock_response.usage.completion_tokens = 3
            mock_response.usage.total_tokens = 8
            mock_response.created = 1234567890
            mock_provider.chat_complete = AsyncMock(return_value=mock_response)
            mock_get_provider.return_value = mock_provider
            
            await router.acompletion(messages=[Message(role="user", content="Test")])
        
        assert hook_called
        assert hook_data["model"] == "gpt-4o-mini"
    
    @pytest.mark.asyncio
    async def test_after_response_hook(self):
        """Test after_response hook is called."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        
        hook_called = False
        hook_response = None
        
        def after_hook(response, **kwargs):
            nonlocal hook_called, hook_response
            hook_called = True
            hook_response = response
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        router.add_hook("after_response", after_hook)
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            mock_response = Mock()
            mock_response.id = "test"
            mock_response.model = "gpt-4o-mini"
            mock_response.choices = [{"message": Message(role="assistant", content="Hi")}]
            mock_response.usage.prompt_tokens = 5
            mock_response.usage.completion_tokens = 3
            mock_response.usage.total_tokens = 8
            mock_response.created = 1234567890
            mock_provider.chat_complete = AsyncMock(return_value=mock_response)
            mock_get_provider.return_value = mock_provider
            
            await router.acompletion(messages=[Message(role="user", content="Test")])
        
        assert hook_called
        assert hook_response.id == "test"
    
    @pytest.mark.asyncio
    async def test_on_error_hook(self):
        """Test on_error hook is called on failure."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        
        hook_called = False
        hook_error = None
        
        def error_hook(error, model: str, **kwargs):
            nonlocal hook_called, hook_error
            hook_called = True
            hook_error = error
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        router.add_hook("on_error", error_hook)
        
        with patch.object(router, '_get_provider') as mock_get_provider:
            mock_provider = AsyncMock()
            test_error = Exception("Test error")
            mock_provider.chat_complete = AsyncMock(side_effect=test_error)
            mock_get_provider.return_value = mock_provider
            
            with pytest.raises(Exception):
                await router.acompletion(messages=[Message(role="user", content="Test")])
        
        assert hook_called
        assert hook_error == test_error


class TestMockMode:
    """Test mock mode for easy testing without API calls."""
    
    @pytest.mark.asyncio
    async def test_mock_mode_returns_predefined_response(self):
        """Test that mock mode returns predefined responses."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        from good_agent.llm_client.types.chat import ChatResponse
        from good_agent.llm_client.types.common import Usage
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        
        # Set mock response
        mock_response = ChatResponse(
            id="mock-123",
            model="gpt-4o-mini",
            choices=[{"message": Message(role="assistant", content="Mocked response")}],
            usage=Usage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            created=1234567890
        )
        
        router.set_mock_response(mock_response)
        
        # Make request - should return mock without calling provider
        response = await router.acompletion(
            messages=[Message(role="user", content="Test")]
        )
        
        assert response.id == "mock-123"
        assert response.choices[0]["message"].content == "Mocked response"
    
    @pytest.mark.asyncio
    async def test_mock_mode_with_function(self):
        """Test mock mode with a function for dynamic responses."""
        from good_agent.llm_client.router import Router
        from good_agent.llm_client.types.common import Message
        from good_agent.llm_client.types.chat import ChatResponse
        from good_agent.llm_client.types.common import Usage
        
        router = Router(models=["gpt-4o-mini"], api_key="test-key")
        
        call_count = 0
        
        def mock_fn(messages, model, **kwargs):
            nonlocal call_count
            call_count += 1
            return ChatResponse(
                id=f"mock-{call_count}",
                model=model,
                choices=[{"message": Message(role="assistant", content=f"Response {call_count}")}],
                usage=Usage(prompt_tokens=5, completion_tokens=10, total_tokens=15),
                created=1234567890
            )
        
        router.set_mock_response(mock_fn)
        
        # Make multiple requests
        response1 = await router.acompletion(messages=[Message(role="user", content="Test 1")])
        response2 = await router.acompletion(messages=[Message(role="user", content="Test 2")])
        
        assert response1.id == "mock-1"
        assert response2.id == "mock-2"
        assert call_count == 2
