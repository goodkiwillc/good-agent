from good_agent.agent import Agent
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)
from good_agent.tools import ToolCall, ToolCallFunction
from good_agent.utilities.tokens import (
    count_text_tokens,
    get_message_token_count,
    message_to_dict,
)


class TestTextTokenCounting:
    """Test plain text token counting."""

    def test_count_empty_string(self):
        """Test counting tokens in empty string."""
        count = count_text_tokens("", model="gpt-4o")
        assert count == 0

    def test_count_simple_text(self):
        """Test counting tokens in simple text."""
        text = "Hello, world!"
        count = count_text_tokens(text, model="gpt-4o")
        assert count > 0
        assert count < 10  # Should be a few tokens

    def test_count_long_text(self):
        """Test counting tokens in longer text."""
        text = "This is a longer piece of text that should contain more tokens. " * 10
        count = count_text_tokens(text, model="gpt-4o")
        assert count > 50  # Should be many tokens

    def test_caching_works(self):
        """Test that token counting is cached for identical text."""
        text = "Test caching behavior"

        # First call - will compute
        count1 = count_text_tokens(text, model="gpt-4o")

        # Second call - should use cache
        count2 = count_text_tokens(text, model="gpt-4o")

        assert count1 == count2

    def test_different_models(self):
        """Test that different models may produce different counts."""
        text = "Test model differences"

        count_gpt4o = count_text_tokens(text, model="gpt-4o")
        count_gpt35 = count_text_tokens(text, model="gpt-3.5-turbo")

        # Counts should be similar but may differ slightly
        assert count_gpt4o > 0
        assert count_gpt35 > 0


class TestMessageTokenCounting:
    """Test message-level token counting."""

    def test_user_message_simple(self):
        """Test counting tokens in simple user message."""
        msg = UserMessage("Hello, how are you?")
        count = len(msg)
        assert count > 0
        assert count < 20

    def test_user_message_multiline(self):
        """Test counting tokens in multiline user message."""
        msg = UserMessage(
            "This is line 1\nThis is line 2\nThis is line 3\nThis is line 4"
        )
        count = len(msg)
        assert count > 10

    def test_system_message(self):
        """Test counting tokens in system message."""
        msg = SystemMessage("You are a helpful assistant.")
        count = len(msg)
        assert count > 0
        assert count < 20

    def test_assistant_message_no_tools(self):
        """Test counting tokens in assistant message without tools."""
        msg = AssistantMessage("I'm doing well, thank you!")
        count = len(msg)
        assert count > 0
        assert count < 20

    def test_assistant_message_with_tool_calls(self):
        """Test counting tokens in assistant message with tool calls."""
        tool_call = ToolCall(
            id="call_123",
            function=ToolCallFunction(
                name="get_weather",
                arguments='{"location": "San Francisco", "unit": "celsius"}',
            ),
        )

        msg = AssistantMessage(
            "Let me check the weather for you.", tool_calls=[tool_call]
        )

        # Count with tools
        count_with_tools = get_message_token_count(msg, include_tools=True)
        # Count without tools
        count_without_tools = get_message_token_count(msg, include_tools=False)

        assert count_with_tools > count_without_tools
        assert count_with_tools > 10

    def test_tool_message(self):
        """Test counting tokens in tool message."""
        msg = ToolMessage(
            '{"temperature": 72, "conditions": "sunny"}',
            tool_call_id="call_123",
            tool_name="get_weather",
        )

        count = len(msg)
        assert count > 0

    def test_message_caching(self):
        """Test that message token counts are cached."""
        msg = UserMessage("Test message for caching")

        # First call - computes and caches
        count1 = len(msg)

        # Check that cache was created
        assert hasattr(msg, "_token_count_cache")
        assert len(msg._token_count_cache) > 0

        # Second call - uses cache
        count2 = len(msg)

        assert count1 == count2

    def test_message_dict_conversion(self):
        """Test converting message to dict format."""
        msg = UserMessage("Hello!")
        msg_dict = message_to_dict(msg)

        assert msg_dict["role"] == "user"
        assert msg_dict["content"] == "Hello!"
        assert "tool_calls" not in msg_dict

    def test_message_dict_with_tools(self):
        """Test converting assistant message with tools to dict."""
        tool_call = ToolCall(
            id="call_456",
            function=ToolCallFunction(name="search", arguments='{"query": "test"}'),
        )

        msg = AssistantMessage("Searching...", tool_calls=[tool_call])
        msg_dict = message_to_dict(msg, include_tools=True)

        assert msg_dict["role"] == "assistant"
        assert "tool_calls" in msg_dict
        assert len(msg_dict["tool_calls"]) == 1
        assert msg_dict["tool_calls"][0]["function"]["name"] == "search"


class TestAgentTokenCounting:
    """Test agent-level token counting."""

    def test_agent_len_empty(self):
        """Test token count of empty agent."""
        agent = Agent()
        count = len(agent)
        assert count >= 0  # Empty agent has at least system message overhead

    def test_agent_len_with_messages(self):
        """Test token count of agent with messages."""
        agent = Agent()
        agent.append("Hello, assistant!")
        agent.append("Hi! How can I help you?", role="assistant")

        count = len(agent)
        assert count > 0

    def test_get_token_count_basic(self):
        """Test basic token count retrieval."""
        agent = Agent()
        agent.system.set("You are a helpful assistant.")
        agent.append("What is 2+2?")

        count = agent.get_token_count()
        assert count > 0

    def test_get_token_count_exclude_system(self):
        """Test token count excluding system messages."""
        agent = Agent()
        agent.system.set("You are a helpful assistant with detailed instructions.")
        agent.append("Hello")

        count_all = agent.get_token_count(include_system=True)
        count_no_system = agent.get_token_count(include_system=False)

        assert count_all > count_no_system

    def test_get_token_count_by_role(self):
        """Test getting token counts by role."""
        agent = Agent()
        agent.system.set("You are helpful.")
        agent.append("Hello!")
        agent.append("Hi there!", role="assistant")
        agent.append("How are you?")

        counts = agent.get_token_count_by_role()

        assert "system" in counts
        assert "user" in counts
        assert "assistant" in counts
        assert "tool" in counts

        assert counts["system"] > 0
        assert counts["user"] > 0
        assert counts["assistant"] > 0
        assert counts["tool"] == 0  # No tool messages

    def test_get_token_count_subset_messages(self):
        """Test counting tokens for subset of messages."""
        agent = Agent()
        agent.append("Message 1")
        agent.append("Message 2")
        agent.append("Message 3")

        # Count only first two messages
        subset_count = agent.get_token_count(messages=agent.messages[:2])

        # Count all messages
        all_count = agent.get_token_count()

        assert subset_count < all_count
        assert subset_count > 0


class TestTokenCountingWithTemplates:
    """Test token counting with template messages."""

    def test_template_message_renders_before_counting(self):
        """Test that templates are rendered before counting tokens."""
        agent = Agent()
        agent.context["name"] = "Alice"

        msg = UserMessage(template="Hello, {{ name }}!")
        agent.append(msg)

        count = len(msg)

        # The rendered content should be "Hello, Alice!" not the raw template
        assert count > 0
        # Template should be rendered in token count
        assert count < 20


class TestCachingBehavior:
    """Test caching behavior and performance."""

    def test_repeated_calls_use_cache(self):
        """Test that repeated len() calls use cached values."""
        msg = UserMessage("Test message for performance")

        # First call
        count1 = len(msg)

        # Verify cache exists
        assert hasattr(msg, "_token_count_cache")
        cache_key = "gpt-4o:True"  # model:include_tools
        assert cache_key in msg._token_count_cache

        # Second call should use cache
        count2 = len(msg)

        assert count1 == count2

    def test_different_models_cache_separately(self):
        """Test that different models maintain separate caches."""
        msg = UserMessage("Test multi-model caching")

        # Count with different models
        count_gpt4o = get_message_token_count(msg, model="gpt-4o")
        count_gpt35 = get_message_token_count(msg, model="gpt-3.5-turbo")

        # Should have two cache entries
        assert hasattr(msg, "_token_count_cache")
        assert len(msg._token_count_cache) == 2

    def test_include_tools_flag_cache_separately(self):
        """Test that include_tools flag maintains separate caches."""
        tool_call = ToolCall(
            id="call_789",
            function=ToolCallFunction(name="test", arguments="{}"),
        )
        msg = AssistantMessage("Test", tool_calls=[tool_call])

        count_with = get_message_token_count(msg, include_tools=True)
        count_without = get_message_token_count(msg, include_tools=False)

        assert count_with > count_without
        assert len(msg._token_count_cache) == 2
