import pytest

from good_agent import Agent


class TestSpecCompliantMockAPI:
    """Test the spec-compliant mock API (agent.mock.create, agent.mock.tool_call)"""

    @pytest.mark.asyncio
    async def test_agent_mock_interface_exists(self):
        """Test that agent.mock is an interface object with expected methods"""
        async with Agent("System prompt") as agent:
            # Check mock interface exists
            assert hasattr(agent, "mock")
            assert hasattr(agent.mock, "create")
            assert hasattr(agent.mock, "tool_call")
            assert callable(agent.mock)  # __call__ method for agent.mock()

    @pytest.mark.asyncio
    async def test_agent_mock_create(self):
        """Test agent.mock.create() method"""
        async with Agent("System prompt") as agent:
            # Simple message creation
            msg = agent.mock.create("Hello world")
            assert msg.content == "Hello world"
            assert msg.role == "assistant"
            assert msg.type == "message"

            # Message with role
            msg = agent.mock.create("Question?", role="user")
            assert msg.content == "Question?"
            assert msg.role == "user"

            # Message with tool calls
            msg = agent.mock.create(
                "I'll check the weather",
                tool_calls=[{"name": "weather", "arguments": {"location": "NYC"}}],
            )
            assert msg.content == "I'll check the weather"
            assert msg.tool_calls is not None
            assert msg.tool_calls is not None and len(msg.tool_calls) == 1
            assert msg.tool_calls[0]["tool_name"] == "weather"
            assert msg.tool_calls[0]["arguments"] == {"location": "NYC"}

    @pytest.mark.asyncio
    async def test_agent_mock_tool_call(self):
        """Test agent.mock.tool_call() method"""
        async with Agent("System prompt") as agent:
            # Simple tool call
            call = agent.mock.tool_call("calculator", arguments={"expr": "2+2"})
            assert call.type == "tool_call"
            assert call.tool_name == "calculator"
            assert call.tool_arguments == {"expr": "2+2"}
            assert call.tool_result == "Mock result"
            assert call.tool_call_id is not None

            # Tool call with custom result
            call = agent.mock.tool_call(
                "weather",
                arguments={"location": "NYC"},
                result={"temp": 72, "condition": "sunny"},
            )
            assert call.tool_result == {"temp": 72, "condition": "sunny"}

            # Tool call with kwargs as arguments
            call = agent.mock.tool_call("search", query="python", limit=10)
            assert call.tool_arguments == {"query": "python", "limit": 10}

            # Mixed arguments and kwargs
            call = agent.mock.tool_call(
                "advanced_search", arguments={"query": "python"}, limit=10, sort="date"
            )
            assert call.tool_arguments == {
                "query": "python",
                "limit": 10,
                "sort": "date",
            }

    @pytest.mark.asyncio
    async def test_agent_mock_call_creates_context_manager(self):
        """Test that agent.mock() creates a context manager"""
        async with Agent("System prompt") as agent:
            # Test with mock responses
            mock_ctx = agent.mock(
                agent.mock.create("Response 1"),
                agent.mock.tool_call("tool", result="result"),
                agent.mock.create("Response 2"),
            )

            assert hasattr(mock_ctx, "__enter__")
            assert hasattr(mock_ctx, "__exit__")

            # Test context manager usage
            with mock_ctx as mock_agent:
                assert hasattr(mock_agent, "execute")
                assert hasattr(mock_agent, "call")
                assert mock_agent.agent is agent
                assert len(mock_agent.responses) == 3

    @pytest.mark.asyncio
    async def test_spec_example_usage(self):
        """Test the exact usage pattern from the spec"""
        async with Agent("System prompt") as agent:
            # This is the exact pattern from the spec
            mock_ctx = agent.mock(
                agent.mock.create(
                    "I'll check the weather",
                    tool_calls=[{"name": "get_weather", "arguments": {"location": "NYC"}}],
                ),
                agent.mock.tool_call(
                    "get_weather",
                    location="NYC",  # kwargs style
                    result={"temp": 72, "condition": "sunny"},
                ),
                agent.mock.create("The weather in NYC is 72°F and sunny!"),
            )

            with mock_ctx as mock_agent:
                responses = mock_agent.responses

                # Check first message
                assert responses[0].type == "message"
                assert responses[0].content == "I'll check the weather"
                assert responses[0].tool_calls is not None and len(responses[0].tool_calls) == 1

                # Check tool call
                assert responses[1].type == "tool_call"
                assert responses[1].tool_name == "get_weather"
                assert responses[1].tool_arguments == {"location": "NYC"}
                assert responses[1].tool_result == {"temp": 72, "condition": "sunny"}

                # Check final message
                assert responses[2].type == "message"
                assert responses[2].content == "The weather in NYC is 72°F and sunny!"

    @pytest.mark.asyncio
    async def test_agent_mock_string_conversion(self):
        """Test backwards compatibility with string conversion"""
        async with Agent("System prompt") as agent:
            # Mix of explicit mocks and strings
            mock_ctx = agent.mock(
                "Simple string response",  # Should be converted
                agent.mock.create("Explicit message"),
                agent.mock.tool_call("tool", result="result"),
            )

            with mock_ctx as mock_agent:
                assert len(mock_agent.responses) == 3

                # Check string was converted
                assert mock_agent.responses[0].type == "message"
                assert mock_agent.responses[0].content == "Simple string response"
                assert mock_agent.responses[0].role == "assistant"

    @pytest.mark.asyncio
    async def test_invalid_tool_call_format(self):
        """Test validation of tool call format in create()"""
        async with Agent("System prompt") as agent:
            with pytest.raises(ValueError, match="Invalid tool call format"):
                agent.mock.create(
                    "Message",
                    tool_calls=[
                        {"invalid": "format"}  # Missing 'name' and 'arguments'
                    ],
                )

    @pytest.mark.asyncio
    async def test_mock_interface_agent_reference(self):
        """Test that mock interface maintains reference to agent"""
        async with Agent("System prompt") as agent:
            assert agent.mock.agent is agent

    @pytest.mark.asyncio
    async def test_spec_compliant_execution(self):
        """Test that the spec example actually works end-to-end"""
        agent = Agent("System prompt")

        try:
            # This is the exact pattern from the spec - and it should work
            with agent.mock(
                agent.mock.create(
                    "I'll check the weather",
                    tool_calls=[{"name": "get_weather", "arguments": {"location": "NYC"}}],
                ),
                agent.mock.tool_call(
                    "get_weather",
                    location="NYC",
                    result={"temp": 72, "condition": "sunny"},
                ),
                agent.mock.create("The weather in NYC is 72°F and sunny!"),
            ) as mock_agent:
                # Test call() returns first assistant message
                result = await mock_agent.call()
                assert result.content == "I'll check the weather"
                assert result.tool_calls is not None and len(result.tool_calls) == 1

                # Test execute() yields all messages in conversation flow
                messages = []
                async for message in mock_agent.execute():
                    messages.append(message)

                assert len(messages) == 3
                assert messages[0].content == "I'll check the weather"
                assert messages[1].role == "tool"
                assert messages[2].content == "The weather in NYC is 72°F and sunny!"
        finally:
            # Clean up Observable tasks
            await agent.events.close()


class TestMockVsTestingFixtures:
    """
    Clarify the distinction between:
    1. Built-in mocking (agent.mock) - for testing agent conversation flows
    2. Testing fixtures - for testing LLM integration by mocking LanguageModel/litellm
    """

    def test_builtin_mock_purpose(self):
        """Built-in mock is for testing conversation flows without LLM calls"""
        agent = Agent("System prompt")

        try:
            # This is for testing agent behavior - conversation flow, message handling, etc.
            # WITHOUT making actual LLM API calls
            with agent.mock(agent.mock.create("Mocked response", role="assistant")) as mock_agent:
                # This will use pre-programmed responses instead of calling LLM
                assert isinstance(mock_agent.responses[0].content, str)
        finally:
            # Clean up Observable tasks
            agent.events.join_sync()

    def test_testing_fixtures_purpose(self):
        """Testing fixtures would be for mocking the LanguageModel/litellm layer"""
        # For testing actual LLM integration, we would:
        # 1. Mock/patch the LanguageModel.complete() method
        # 2. Mock/patch litellm calls
        # 3. Use dependency injection to replace LanguageModel instance

        # This is different from agent.mock - this tests the LLM integration layer
        # while agent.mock tests the conversation flow layer

        # Example (not implemented yet):
        # with patch.object(agent.model, 'complete') as mock_complete:
        #     mock_complete.return_value = LLMResponse(...)
        #     result = await agent.call("Test message")

        assert True  # Placeholder - actual implementation would be different
