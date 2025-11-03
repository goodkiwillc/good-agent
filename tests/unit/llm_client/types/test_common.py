"""
Tests for common types (RED phase - write tests first).

These tests will initially fail until we implement the types.
"""

import pytest
from typing import Any


class TestUsage:
    """Test Usage model."""
    
    def test_usage_creation(self):
        """Test creating a Usage instance."""
        from good_agent.llm_client.types.common import Usage
        
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
    
    def test_usage_optional_fields(self):
        """Test Usage with optional cache fields."""
        from good_agent.llm_client.types.common import Usage
        
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            prompt_tokens_details={"cached_tokens": 20},
            completion_tokens_details={"reasoning_tokens": 10}
        )
        
        assert usage.prompt_tokens_details == {"cached_tokens": 20}
        assert usage.completion_tokens_details == {"reasoning_tokens": 10}
    
    def test_usage_defaults(self):
        """Test Usage with only required fields."""
        from good_agent.llm_client.types.common import Usage
        
        usage = Usage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150
        )
        
        assert usage.prompt_tokens_details is None
        assert usage.completion_tokens_details is None


class TestMessage:
    """Test Message model."""
    
    def test_message_simple_text(self):
        """Test simple text message."""
        from good_agent.llm_client.types.common import Message
        
        msg = Message(role="user", content="Hello, world!")
        
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.name is None
        assert msg.tool_calls is None
        assert msg.tool_call_id is None
    
    def test_message_with_name(self):
        """Test message with name field."""
        from good_agent.llm_client.types.common import Message
        
        msg = Message(role="user", content="Hello", name="John")
        
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.name == "John"
    
    def test_message_with_tool_calls(self):
        """Test assistant message with tool calls."""
        from good_agent.llm_client.types.common import Message
        
        tool_calls = [
            {
                "id": "call_123",
                "type": "function",
                "function": {"name": "get_weather", "arguments": '{"city": "SF"}'}
            }
        ]
        
        msg = Message(role="assistant", content=None, tool_calls=tool_calls)
        
        assert msg.role == "assistant"
        assert msg.content is None
        assert msg.tool_calls == tool_calls
    
    def test_message_tool_response(self):
        """Test tool response message."""
        from good_agent.llm_client.types.common import Message
        
        msg = Message(
            role="tool",
            content="Temperature is 72°F",
            tool_call_id="call_123",
            name="get_weather"
        )
        
        assert msg.role == "tool"
        assert msg.content == "Temperature is 72°F"
        assert msg.tool_call_id == "call_123"
        assert msg.name == "get_weather"


class TestModelResponse:
    """Test ModelResponse model."""
    
    def test_model_response_basic(self):
        """Test basic model response."""
        from good_agent.llm_client.types.common import ModelResponse, Message, Usage
        
        response = ModelResponse(
            id="chatcmpl-123",
            model="gpt-4o-mini",
            choices=[{"message": Message(role="assistant", content="Hello!")}],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            created=1234567890
        )
        
        assert response.id == "chatcmpl-123"
        assert response.model == "gpt-4o-mini"
        assert len(response.choices) == 1
        assert response.choices[0]["message"].content == "Hello!"
        assert response.usage.total_tokens == 15
        assert response.created == 1234567890
    
    def test_model_response_optional_fields(self):
        """Test ModelResponse with optional metadata."""
        from good_agent.llm_client.types.common import ModelResponse, Message, Usage
        
        response = ModelResponse(
            id="chatcmpl-123",
            model="gpt-4o-mini",
            choices=[{"message": Message(role="assistant", content="Hello!")}],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            created=1234567890,
            system_fingerprint="fp_123",
            response_metadata={"provider": "openai"}
        )
        
        assert response.system_fingerprint == "fp_123"
        assert response.response_metadata == {"provider": "openai"}
    
    def test_model_response_get_content(self):
        """Test getting content from response."""
        from good_agent.llm_client.types.common import ModelResponse, Message, Usage
        
        response = ModelResponse(
            id="chatcmpl-123",
            model="gpt-4o-mini",
            choices=[{"message": Message(role="assistant", content="Test response")}],
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            created=1234567890
        )
        
        # Should be able to access first choice message
        first_choice = response.choices[0]
        assert first_choice["message"].content == "Test response"
        assert first_choice["message"].role == "assistant"
