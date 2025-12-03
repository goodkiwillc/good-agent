import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage, ToolMessage, UserMessage
from good_agent.tools import ToolCall, ToolCallFunction, tool
from litellm.types.utils import Choices
from litellm.utils import Message as LiteLLMMessage


class MockLLMResponse:
    """Mock response from litellm"""

    def __init__(self, content="Test response", tool_calls=None):
        # Create proper Choices and Message objects
        message = LiteLLMMessage()
        message.content = content
        message.tool_calls = tool_calls or []

        choice = Choices()
        choice.message = message
        choice.provider_specific_fields = {}

        self.choices = [choice]


@pytest.fixture
def mock_litellm():
    """Mock litellm for testing"""
    with patch("good_agent.llm.LanguageModel.litellm") as mock:
        # Return the mock itself so we can configure it per test
        yield mock


async def create_test_agent():
    """Create agent with test tools"""
    # Clear the global registry instance to avoid conflicts
    import good_agent.tools.registry

    good_agent.tools.registry._global_registry = None

    @tool
    def get_weather(location: str) -> str:
        """Get current weather for a location"""
        return f"The weather in {location} is sunny and 72°F"

    @tool
    def calculate(expression: str) -> str:
        """Calculate a mathematical expression"""
        try:
            result = eval(expression)
            return f"Result: {result}"
        except Exception:
            return "Error: Invalid expression"

    # Return context manager directly instead of initialized agent
    return Agent(
        "You are a helpful assistant with weather and calculation tools.",
        tools=[get_weather, calculate],
    )


class TestLLMIntegration:
    """Test actual LLM integration in call() method"""

    @pytest.mark.asyncio
    async def test_call_simple_response(self):
        """Test simple call without tools"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Mock the LLM response
            mock_response = MockLLMResponse(content="Hello! How can I help you today?")

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(return_value=mock_response),
            ):
                # Make the call
                response = await agent_with_tools.call("Hello")

                # Verify response
                assert isinstance(response, AssistantMessage)
                assert response.content == "Hello! How can I help you today?"
                assert response.tool_calls is None

                # Verify message was added to conversation
                assert len(agent_with_tools.messages) == 3  # system + user + assistant
                assert agent_with_tools.messages[-1] == response

    @pytest.mark.asyncio
    async def test_call_with_tool_calls(self):
        """Test call that returns tool calls"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create mock tool calls
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_123"
            mock_tool_call.type = "function"
            mock_tool_call.function.name = "get_weather"
            mock_tool_call.function.arguments = json.dumps({"location": "New York"})

            mock_response = MockLLMResponse(
                content="I'll check the weather for you.", tool_calls=[mock_tool_call]
            )

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(return_value=mock_response),
            ):
                # Make the call
                response = await agent_with_tools.call("What's the weather in New York?")

                # Verify response
                assert isinstance(response, AssistantMessage)
                assert response.content == "I'll check the weather for you."
                assert response.tool_calls is not None
                assert len(response.tool_calls) == 1

                # Verify tool call details
                tool_call = response.tool_calls[0]
                assert tool_call.id == "call_123"
                assert tool_call.type == "function"
                assert tool_call.function.name == "get_weather"
                assert tool_call.function.arguments == '{"location": "New York"}'

    @pytest.mark.asyncio
    async def test_call_with_context(self):
        """Test call with custom context"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            mock_response = MockLLMResponse(content="Response with context")

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(return_value=mock_response),
            ) as mock_complete:
                # Make the call with context
                await agent_with_tools.call(
                    "Test message", context={"user_name": "Alice"}, temperature=0.5
                )

                # Verify LLM was called with correct parameters
                mock_complete.assert_called_once()
                call_args = mock_complete.call_args

                # Check temperature was passed through
                assert call_args[1]["temperature"] == 0.5

                # Check tools were included
                assert "tools" in call_args[1]
                assert len(call_args[1]["tools"]) == 2

    @pytest.mark.asyncio
    async def test_messages_to_litellm_conversion(self):
        """Test message conversion to litellm format"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Add various message types
            agent_with_tools.append("User message", role="user")

            # Add assistant message with tool calls
            tool_call = ToolCall(
                id="call_456",
                type="function",
                function=ToolCallFunction(name="calculate", arguments='{"expression": "2 + 2"}'),
            )
            agent_with_tools.messages.append(
                AssistantMessage(content="Let me calculate that", tool_calls=[tool_call])
            )

            # Add tool response
            agent_with_tools.messages.append(
                ToolMessage(
                    content="Result: 4",
                    tool_call_id="call_456",
                    tool_name="calculate",
                )
            )

            # Convert messages
            litellm_messages = await agent_with_tools.model.format_message_list_for_llm(
                agent_with_tools.messages
            )

            # Verify conversion
            assert len(litellm_messages) == 4  # system + user + assistant + tool

            # Check system message
            assert litellm_messages[0]["role"] == "system"
            assert "helpful assistant" in litellm_messages[0]["content"]

            # Check user message - now returns content as list for multimodal support
            assert litellm_messages[1]["role"] == "user"
            assert litellm_messages[1]["content"][0]["type"] == "text"
            assert litellm_messages[1]["content"][0]["text"] == "User message"

            # Check assistant message with tool calls
            assert litellm_messages[2]["role"] == "assistant"
            assert litellm_messages[2]["content"] == "Let me calculate that"
            assert "tool_calls" in litellm_messages[2]
            assert len(litellm_messages[2]["tool_calls"]) == 1
            assert litellm_messages[2]["tool_calls"][0]["id"] == "call_456"
            assert litellm_messages[2]["tool_calls"][0]["function"]["name"] == "calculate"

            # Check tool message
            assert litellm_messages[3]["role"] == "tool"
            assert litellm_messages[3]["content"] == "Result: 4"
            assert litellm_messages[3]["tool_call_id"] == "call_456"


class TestExecuteMethod:
    """Test the execute() method with automatic tool execution"""

    @pytest.mark.asyncio
    async def test_execute_simple_conversation(self):
        """Test execute without tool calls - stops after first response with no tool calls"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Mock response without tool calls
            mock_response = MockLLMResponse("Hello! How can I help?")

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(return_value=mock_response),
            ):
                # Execute and collect messages
                messages = []
                async for msg in agent_with_tools.execute(max_iterations=2):
                    messages.append(msg)

                # Should get 1 assistant message (stops when no tool calls)
                assert len(messages) == 1
                assert isinstance(messages[0], AssistantMessage)
                assert messages[0].content == "Hello! How can I help?"

    @pytest.mark.asyncio
    async def test_execute_with_tool_execution(self):
        """Test execute with automatic tool execution"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create tool call
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_789"
            mock_tool_call.type = "function"
            mock_tool_call.function.name = "get_weather"
            mock_tool_call.function.arguments = json.dumps({"location": "London"})

            # Mock responses - first with tool call, then final response
            responses = [
                MockLLMResponse(
                    "I'll check the weather in London for you.",
                    tool_calls=[mock_tool_call],
                ),
                MockLLMResponse("The weather in London is sunny and 72°F. It's a beautiful day!"),
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                # Execute and collect messages
                messages = []
                async for msg in agent_with_tools.execute():
                    messages.append(msg)

                # Should get: assistant (with tool call) -> tool response -> assistant (final)
                assert len(messages) == 3

                # First message: assistant with tool call
                assert isinstance(messages[0], AssistantMessage)
                assert messages[0].content == "I'll check the weather in London for you."
                assert messages[0].tool_calls is not None
                assert len(messages[0].tool_calls) == 1

                # Second message: tool response
                assert isinstance(messages[1], ToolMessage)
                assert messages[1].content == "The weather in London is sunny and 72°F"
                assert messages[1].tool_call_id == "call_789"
                assert messages[1].tool_name == "get_weather"

                # Third message: final assistant response
                assert isinstance(messages[2], AssistantMessage)
                assert "sunny and 72°F" in messages[2].content

    @pytest.mark.asyncio
    async def test_execute_multiple_tool_calls(self):
        """Test execute with multiple tool calls in one response"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create multiple tool calls
            weather_call = MagicMock()
            weather_call.id = "call_001"
            weather_call.type = "function"
            weather_call.function.name = "get_weather"
            weather_call.function.arguments = json.dumps({"location": "Paris"})

            calc_call = MagicMock()
            calc_call.id = "call_002"
            calc_call.type = "function"
            calc_call.function.name = "calculate"
            calc_call.function.arguments = json.dumps({"expression": "32 * 1.8 + 32"})

            # Mock responses
            responses = [
                MockLLMResponse(
                    "I'll check the weather and convert the temperature.",
                    tool_calls=[weather_call, calc_call],
                ),
                MockLLMResponse(
                    "The weather in Paris is sunny and 72°F, which is 89.6°F when converted."
                ),
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                messages = []
                async for msg in agent_with_tools.execute():
                    messages.append(msg)

                # Should get: assistant -> tool1 -> tool2 -> assistant
                assert len(messages) == 4

                # Verify tool responses
                tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
                assert len(tool_messages) == 2
                assert any("Paris" in m.content for m in tool_messages)
                assert any("89.6" in str(m.content) for m in tool_messages)

    @pytest.mark.asyncio
    async def test_execute_tool_error_handling(self):
        """Test execute handles tool execution errors gracefully"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create tool call with invalid arguments
            bad_call = MagicMock()
            bad_call.id = "call_bad"
            bad_call.type = "function"
            bad_call.function.name = "calculate"
            bad_call.function.arguments = json.dumps({"expression": "invalid/0"})

            responses = [
                MockLLMResponse("Let me calculate that.", tool_calls=[bad_call]),
                MockLLMResponse("I encountered an error with the calculation."),
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                messages = []
                async for msg in agent_with_tools.execute():
                    messages.append(msg)

                # Should still get tool message with error
                tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
                assert len(tool_msgs) == 1
                assert "Error" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test execute handles unknown tool gracefully"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create tool call for non-existent tool
            unknown_call = MagicMock()
            unknown_call.id = "call_unknown"
            unknown_call.type = "function"
            unknown_call.function.name = "unknown_tool"
            unknown_call.function.arguments = "{}"

            responses = [
                MockLLMResponse("Using unknown tool.", tool_calls=[unknown_call]),
                MockLLMResponse("The tool was not available."),
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                messages = []
                async for msg in agent_with_tools.execute():
                    messages.append(msg)

                # Should get error message for unknown tool
                tool_msgs = [m for m in messages if isinstance(m, ToolMessage)]
                assert len(tool_msgs) == 1
                assert "not found" in tool_msgs[0].content

    @pytest.mark.asyncio
    async def test_execute_respects_max_iterations(self):
        """Test execute stops at max_iterations when tool calls continue"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create a tool call that keeps generating more tool calls
            def create_tool_call(i):
                mock_call = MagicMock()
                mock_call.id = f"call_{i}"
                mock_call.type = "function"
                mock_call.function.name = "calculate"
                mock_call.function.arguments = json.dumps({"expression": f"{i} + 1"})
                return mock_call

            # Mock continuous responses with tool calls
            responses = [
                MockLLMResponse(f"Calculating {i}...", tool_calls=[create_tool_call(i)])
                for i in range(5)  # More than max_iterations
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                messages = []
                async for msg in agent_with_tools.execute(max_iterations=3):
                    messages.append(msg)

                # Should stop at 3 iterations (3 assistant + 3 tool messages = 6 total)
                assistant_messages = [m for m in messages if isinstance(m, AssistantMessage)]
                assert len(assistant_messages) == 3

                # Each assistant message should have tool calls
                assert all(msg.tool_calls is not None for msg in assistant_messages)

    @pytest.mark.asyncio
    async def test_execute_stops_without_tool_calls(self):
        """Test execute stops when no tool calls are returned"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Mock responses - first with tool call, then without
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_001"
            mock_tool_call.type = "function"
            mock_tool_call.function.name = "get_weather"
            mock_tool_call.function.arguments = json.dumps({"location": "Tokyo"})

            responses = [
                MockLLMResponse("Let me check the weather.", tool_calls=[mock_tool_call]),
                MockLLMResponse(
                    "The weather in Tokyo is sunny and 72°F. Enjoy your day!"
                ),  # No tool calls
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                messages = []
                async for msg in agent_with_tools.execute(max_iterations=10):  # High limit
                    messages.append(msg)

                # Should stop after second response (no tool calls)
                # Messages: assistant with tool call -> tool response -> final assistant
                assert len(messages) == 3
                assert isinstance(messages[0], AssistantMessage)
                assert messages[0].tool_calls is not None
                assert isinstance(messages[1], ToolMessage)
                assert isinstance(messages[2], AssistantMessage)
                assert messages[2].tool_calls is None  # No tool calls, execution stops

    @pytest.mark.asyncio
    async def test_execute_with_conditional_user_message_insertion(self):
        """Test conditionally inserting user messages during execute loop based on content and iteration count"""
        agent_context = await create_test_agent()
        async with agent_context as agent_with_tools:
            # Create tool calls to keep execution going
            tool_call1 = MagicMock()
            tool_call1.id = "call_001"
            tool_call1.type = "function"
            tool_call1.function.name = "calculate"
            tool_call1.function.arguments = json.dumps({"expression": "2 + 2"})

            tool_call2 = MagicMock()
            tool_call2.id = "call_002"
            tool_call2.type = "function"
            tool_call2.function.name = "calculate"
            tool_call2.function.arguments = json.dumps({"expression": "3 + 3"})

            # Mock responses with tool calls to keep execution continuing
            responses = [
                MockLLMResponse("Let me think about that...", tool_calls=[tool_call1]),
                MockLLMResponse(
                    "I need more context. TRIGGER", tool_calls=[tool_call2]
                ),  # Contains trigger word
                MockLLMResponse("Processing additional information..."),
                MockLLMResponse("Based on the additional context, here's my response."),
                MockLLMResponse("All done!"),
            ]

            with patch.object(
                agent_with_tools.model,
                "complete",
                AsyncMock(side_effect=responses),
            ):
                messages_yielded = []
                current_iteration = 0

                # Add initial user message
                agent_with_tools.append("Start the conversation", role="user")

                async for msg in agent_with_tools.execute(max_iterations=10):
                    messages_yielded.append(msg)

                    # Use structural pattern matching for cleaner message handling
                    match msg:
                        case AssistantMessage(i=current_iteration, content=content):
                            # Check for trigger word and iteration condition
                            if "TRIGGER" in str(content) and current_iteration < 4:
                                # Insert a new user message dynamically
                                agent_with_tools.append(
                                    "Here's additional context you requested",
                                    role="user",
                                )

                                # Track that we injected a message
                                msg._conditional_injection_triggered = True  # type: ignore

                        case ToolMessage(content=content, tool_name=_tool_name):
                            # Tool messages could be processed here if needed
                            # For example: print(f"Tool {_tool_name} returned: {content}")
                            pass

                        case _:
                            # Any other message type
                            pass

                    # Stop after we've seen enough iterations
                    if current_iteration >= 4:
                        break

                # Verify the conditional injection happened
                # Find the message that triggered injection
                trigger_messages = [
                    m for m in messages_yielded if hasattr(m, "_conditional_injection_triggered")
                ]
                assert len(trigger_messages) == 1
                assert "TRIGGER" in str(trigger_messages[0].content)

                # Verify the injected user message is in the agent's message history
                user_messages = [m for m in agent_with_tools.messages if isinstance(m, UserMessage)]
                assert len(user_messages) == 2  # Original + injected
                assert "additional context" in user_messages[-1].content

                # Verify execution continued after injection
                assert (
                    len(messages_yielded) >= 3
                )  # At least: first response, trigger response, post-injection response
