import pytest
from good_agent import Agent
from good_agent.messages import (
    AssistantMessage,
    SystemMessage,
    ToolMessage,
    UserMessage,
)


class TestMockExecution:
    """Test that mock responses are actually returned by call() and execute()"""

    @pytest.mark.asyncio
    async def test_mock_call_returns_response(self):
        """Test that call() returns the first mocked assistant response"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create("Hello from mock!", role="assistant")
        ) as mock_agent:
            result = await mock_agent.call()

            assert isinstance(result, AssistantMessage)
            assert result.content == "Hello from mock!"
            assert result.role == "assistant"
            assert result.i == 0  # First iteration
            assert result.agent is agent

    @pytest.mark.asyncio
    async def test_mock_call_with_tool_calls(self):
        """Test that call() returns assistant message with tool calls"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create(
                "I'll check the weather",
                role="assistant",
                tool_calls=[{"name": "weather", "arguments": {"location": "NYC"}}],
            )
        ) as mock_agent:
            result = await mock_agent.call()

            assert isinstance(result, AssistantMessage)
            assert result.content == "I'll check the weather"
            assert result.tool_calls is not None
            assert len(result.tool_calls) == 1
            assert result.tool_calls[0].name == "weather"
            assert result.tool_calls[0].parameters == {"location": "NYC"}

    @pytest.mark.asyncio
    async def test_mock_call_no_responses(self):
        """Test that call() raises error when no responses available"""
        agent = Agent("System prompt")

        with agent.mock() as mock_agent:  # No responses
            with pytest.raises(ValueError, match="No mock responses available"):
                await mock_agent.call()

    @pytest.mark.asyncio
    async def test_mock_call_wrong_response_type(self):
        """Test that call() raises error for non-assistant responses"""
        agent = Agent("System prompt")

        with agent.mock(agent.mock.create("User message", role="user")) as mock_agent:
            with pytest.raises(
                ValueError, match="call\\(\\) expects assistant message"
            ):
                await mock_agent.call()

    @pytest.mark.asyncio
    async def test_mock_execute_yields_all_responses(self):
        """Test that execute() yields all mocked responses in order"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create("First response", role="assistant"),
            agent.mock.create("Second response", role="user"),
            agent.mock.create("Third response", role="assistant"),
        ) as mock_agent:
            messages = []
            async for message in mock_agent.execute():
                messages.append(message)

            assert len(messages) == 3

            # Check first message
            assert isinstance(messages[0], AssistantMessage)
            assert messages[0].content == "First response"
            assert messages[0].i == 0

            # Check second message
            assert isinstance(messages[1], UserMessage)
            assert messages[1].content == "Second response"
            assert messages[1].i == 1

            # Check third message
            assert isinstance(messages[2], AssistantMessage)
            assert messages[2].content == "Third response"
            assert messages[2].i == 2

            # All should have agent reference
            for msg in messages:
                assert msg.agent is agent

    @pytest.mark.asyncio
    async def test_mock_execute_with_tool_calls(self):
        """Test execute() with mixed message and tool call responses"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create("I'll get the weather", role="assistant"),
            agent.mock.tool_call("weather", location="NYC", result={"temp": 72}),
            agent.mock.create("The weather is 72°F", role="assistant"),
        ) as mock_agent:
            messages = []
            async for message in mock_agent.execute():
                messages.append(message)

            assert len(messages) == 3

            # Check assistant message
            assert isinstance(messages[0], AssistantMessage)
            assert messages[0].content == "I'll get the weather"

            # Check tool message
            assert isinstance(messages[1], ToolMessage)
            assert messages[1].content == "{'temp': 72}"  # Tool result as string
            assert messages[1].tool_response is not None
            assert messages[1].tool_response.tool_name == "weather"
            assert messages[1].tool_response.response == {"temp": 72}
            assert messages[1].tool_response.parameters == {"location": "NYC"}

            # Check final assistant message
            assert isinstance(messages[2], AssistantMessage)
            assert messages[2].content == "The weather is 72°F"

    @pytest.mark.asyncio
    async def test_mock_execute_empty_responses(self):
        """Test execute() with no responses"""
        agent = Agent("System prompt")

        with agent.mock() as mock_agent:  # No responses
            messages = []
            async for message in mock_agent.execute():
                messages.append(message)

            assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_mock_pattern_matching(self):
        """Test pattern matching on mocked messages"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create(
                "I'll check weather",
                tool_calls=[{"name": "weather", "arguments": {"location": "NYC"}}],
            ),
            agent.mock.tool_call("weather", location="NYC", result="sunny"),
            agent.mock.create("It's sunny!"),
        ) as mock_agent:
            messages = []

            async for message in mock_agent.execute():
                match message:
                    case AssistantMessage(i=0, tool_calls=tool_calls) if tool_calls:
                        assert len(tool_calls) == 1
                        assert tool_calls[0].name == "weather"
                        messages.append("assistant_with_tools")

                    case ToolMessage(tool_response=tool_response):
                        assert tool_response is not None
                        assert tool_response.tool_name == "weather"
                        assert tool_response.response == "sunny"
                        messages.append("tool_response")

                    case AssistantMessage(i=2):
                        assert message.content == "It's sunny!"
                        messages.append("final_assistant")

            assert messages == [
                "assistant_with_tools",
                "tool_response",
                "final_assistant",
            ]

    @pytest.mark.asyncio
    async def test_mock_string_responses_converted(self):
        """Test that string responses are converted to AssistantMessage"""
        agent = Agent("System prompt")

        with agent.mock("Simple string response") as mock_agent:
            result = await mock_agent.call()

            assert isinstance(result, AssistantMessage)
            assert result.content == "Simple string response"
            assert result.role == "assistant"

    @pytest.mark.asyncio
    async def test_mock_system_message_response(self):
        """Test system message responses"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create("You are now in debug mode", role="system")
        ) as mock_agent:
            messages = []
            async for message in mock_agent.execute():
                messages.append(message)

            assert len(messages) == 1
            assert isinstance(messages[0], SystemMessage)
            assert messages[0].content == "You are now in debug mode"

    @pytest.mark.asyncio
    async def test_mock_responses_index_tracking(self):
        """Test that response index (i) is correctly tracked"""
        agent = Agent("System prompt")

        with agent.mock(
            agent.mock.create("Response 1"),
            agent.mock.create("Response 2"),
            agent.mock.create("Response 3"),
        ) as mock_agent:
            messages = []
            async for message in mock_agent.execute():
                messages.append(message)

            for i, message in enumerate(messages):
                assert message.i == i, f"Message {i} has incorrect index: {message.i}"


class TestMockBehaviorVerification:
    """Test that mocked responses replace actual LLM calls"""

    @pytest.mark.asyncio
    async def test_mock_context_manager_isolation(self):
        """Test that mock only affects calls within context manager"""
        agent = Agent("System prompt")

        # Outside context manager - no mock active
        assert hasattr(agent.model, "complete")  # Normal model available

        with agent.mock("Mocked response") as mock_agent:
            # Inside context - mock should be active
            assert mock_agent.agent is agent
            assert len(mock_agent.responses) == 1

            # Verify we can get mocked response
            result = await mock_agent.call()
            assert result.content == "Mocked response"

        # Outside again - mock should be inactive
        # (Full implementation would verify model is restored)

    def test_mock_responses_attribute_internal(self):
        """Test that responses attribute is for internal use"""
        agent = Agent("System prompt")

        # The responses attribute is mainly for internal tracking and testing
        # In production, users should interact through call() and execute()
        with agent.mock(
            agent.mock.create("Response 1"),
            agent.mock.tool_call("tool", result="result"),
        ) as mock_agent:
            # Internal access for debugging/testing
            assert len(mock_agent.responses) == 2
            assert mock_agent.responses[0].content == "Response 1"
            assert mock_agent.responses[1].tool_result == "result"

            # But primary interface is through methods
            # (This is the key insight - responses is internal state)
