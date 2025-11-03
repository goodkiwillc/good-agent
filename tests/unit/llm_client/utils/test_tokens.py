"""
Tests for token counting (RED phase).

Tests token counting for different providers using lazy-loaded tiktoken.
"""

import pytest
from unittest.mock import Mock, patch


class TestTokenCounting:
    """Test token counting utilities."""
    
    def test_count_tokens_openai_model(self):
        """Test counting tokens for OpenAI models."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        text = "Hello, world! This is a test message."
        count = count_tokens(text, model="gpt-4o-mini")
        
        # Should return a positive integer
        assert isinstance(count, int)
        assert count > 0
        # Rough estimate for this text
        assert 5 < count < 20
    
    def test_count_tokens_different_models(self):
        """Test that different models might have different token counts."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        text = "Hello, world!"
        
        # These use the same encoding but test the model parameter works
        count_gpt4 = count_tokens(text, model="gpt-4")
        count_gpt35 = count_tokens(text, model="gpt-3.5-turbo")
        
        # Should be the same for these models (both use cl100k_base)
        assert count_gpt4 == count_gpt35
    
    def test_count_tokens_empty_string(self):
        """Test counting tokens for empty string."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        count = count_tokens("", model="gpt-4o-mini")
        assert count == 0
    
    def test_count_tokens_long_text(self):
        """Test counting tokens for longer text."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        # Generate a longer text
        text = "This is a test. " * 100  # ~400 words
        count = count_tokens(text, model="gpt-4o-mini")
        
        assert count > 100  # Should be significant
        assert count < 1000  # But not too large
    
    def test_count_message_tokens(self):
        """Test counting tokens in a message list."""
        from good_agent.llm_client.utils.tokens import count_message_tokens
        from good_agent.llm_client.types.common import Message
        
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there! How can I help you?")
        ]
        
        count = count_message_tokens(messages, model="gpt-4o-mini")
        
        assert isinstance(count, int)
        assert count > 0
        # Should include message overhead (role tokens, etc.)
        assert count > 10  # More than just the raw text
    
    def test_count_message_tokens_with_names(self):
        """Test counting tokens with message names."""
        from good_agent.llm_client.utils.tokens import count_message_tokens
        from good_agent.llm_client.types.common import Message
        
        messages = [
            Message(role="system", content="You are helpful.", name="system"),
            Message(role="user", content="Hello", name="Alice")
        ]
        
        count = count_message_tokens(messages, model="gpt-4o-mini")
        assert count > 0
    
    def test_count_message_tokens_with_tool_calls(self):
        """Test counting tokens with tool calls."""
        from good_agent.llm_client.utils.tokens import count_message_tokens
        from good_agent.llm_client.types.common import Message
        
        messages = [
            Message(role="user", content="What's the weather?"),
            Message(
                role="assistant",
                content=None,
                tool_calls=[{
                    "id": "call_123",
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "arguments": '{"city": "San Francisco"}'
                    }
                }]
            )
        ]
        
        count = count_message_tokens(messages, model="gpt-4o-mini")
        assert count > 0
    
    def test_tiktoken_lazy_loading(self):
        """Test that tiktoken is lazily loaded."""
        # Import the module but don't call any functions
        from good_agent.llm_client.utils import tokens
        
        # tiktoken should not be imported yet at module level
        # This is more of a design check - the actual lazy loading
        # happens inside the functions
        assert hasattr(tokens, 'count_tokens')
        assert hasattr(tokens, 'count_message_tokens')
    
    def test_count_tokens_anthropic_approximation(self):
        """Test token counting for Anthropic models (approximation)."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        text = "Hello, world! This is a test."
        count = count_tokens(text, model="claude-3-5-sonnet-20241022")
        
        # Should use approximation
        assert isinstance(count, int)
        assert count > 0
        # Approximation: ~1 token per 4 characters
        assert count < len(text)  # Should be less than character count
    
    def test_count_tokens_unknown_model_fallback(self):
        """Test that unknown models fall back to approximation."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        text = "Hello, world!"
        count = count_tokens(text, model="unknown-model-12345")
        
        # Should use character-based approximation
        assert isinstance(count, int)
        assert count > 0
    
    def test_get_encoding_for_model(self):
        """Test getting encoding for specific models."""
        from good_agent.llm_client.utils.tokens import get_encoding_for_model
        
        # Should return encoding name for known models
        encoding = get_encoding_for_model("gpt-4o-mini")
        assert encoding in ["cl100k_base", "o200k_base", "gpt2", "r50k_base", "p50k_base"]
    
    def test_count_tokens_unicode(self):
        """Test counting tokens with unicode characters."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        text = "Hello, 世界! 🌍"
        count = count_tokens(text, model="gpt-4o-mini")
        
        assert isinstance(count, int)
        assert count > 0
    
    def test_count_tokens_special_characters(self):
        """Test counting tokens with special characters."""
        from good_agent.llm_client.utils.tokens import count_tokens
        
        text = "Code: `print('hello')` and <xml>tags</xml>"
        count = count_tokens(text, model="gpt-4o-mini")
        
        assert isinstance(count, int)
        assert count > 0
