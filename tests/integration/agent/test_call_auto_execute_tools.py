import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage
from good_agent.tools import tool

# Mock LLM response class
from litellm.types.utils import Choices
from litellm.types.utils import Message as LiteLLMMessage


class MockLLMResponse:
    def __init__(self, content, tool_calls=None):
        # Create proper Choices and Message objects
        message = LiteLLMMessage()
        message.content = content
        message.tool_calls = tool_calls
        # model_extra is a property, don't try to set it

        choice = Choices()
        choice.message = message
        choice.provider_specific_fields = {}

        self.choices = [choice]
        self.usage = MagicMock(prompt_tokens=10, completion_tokens=20, total_tokens=30)


async def create_test_agent():
    """Create a test agent with tools."""

    @tool
    async def get_weather(location: str) -> str:
        """Get the current weather for a location."""
        return f"The weather in {location} is sunny and 72°F"

    @tool
    async def calculate(expression: str) -> str:
        """Calculate a mathematical expression."""
        return "42"  # Simplified for testing

    # Return context manager instead of initialized agent
    return Agent(
        "You are a helpful assistant with access to weather and calculation tools.",
        tools=[get_weather, calculate],
    )

    @pytest.mark.asyncio
    async def test_call_auto_executes_tools_by_default(self):
        """Test that call() automatically executes tool calls and returns final response."""
        agent_context = await create_test_agent()
        async with agent_context as agent:
            # Create mock tool call
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_123"
            mock_tool_call.type = "function"
            mock_tool_call.function.name = "get_weather"
            mock_tool_call.function.arguments = json.dumps({"location": "New York"})

            # Mock responses: first with tool call, then final response
            responses = [
                # First call returns tool request
                MockLLMResponse(
                    "I'll check the weather for you.", tool_calls=[mock_tool_call]
                ),
                # Second call returns final response after tool execution
                MockLLMResponse(
                    "Based on my check, the weather in New York is sunny and 72°F. It's a beautiful day!"
                ),
            ]

            with patch.object(
                agent.model, "complete", AsyncMock(side_effect=responses)
            ):
                # Call should automatically execute tools and return final response
                response = await agent.call("What's the weather in New York?")

                # Verify we got the final response, not the intermediate one
                assert isinstance(response, AssistantMessage)
                assert "beautiful day" in response.content
                assert response.tool_calls is None  # Final response has no tool calls

                # Verify the conversation history contains all messages
                assert (
                    len(agent.messages) == 5
                )  # System, User, Assistant with tool call, Tool result, Final Assistant

                # Check message types in order
                assert agent.messages[0].role == "system"
                assert agent.messages[1].role == "user"
                assert agent.messages[2].role == "assistant"  # Assistant with tool call

                # The first assistant message (index -2) should have tool calls
                assert agent.assistant[-2].tool_calls is not None
                assert agent.messages[3].role == "tool"  # Tool result


@pytest.mark.asyncio
async def test_call_with_auto_execute_false():
    """Test that call() returns tool calls without executing when auto_execute_tools=False."""
    agent_context = await create_test_agent()
    async with agent_context as agent:
        # Create mock tool call
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_456"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "calculate"
        mock_tool_call.function.arguments = json.dumps({"expression": "2 + 2"})

        mock_response = MockLLMResponse(
            "I'll calculate that for you.", tool_calls=[mock_tool_call]
        )

        with patch.object(
            agent.model, "complete", AsyncMock(return_value=mock_response)
        ):
            # Call with auto_execute_tools=False should return tool calls without executing
            response = await agent.call("What is 2 + 2?", auto_execute_tools=False)

            # Verify we got the response with tool calls
            assert isinstance(response, AssistantMessage)
            assert response.content == "I'll calculate that for you."
            assert response.tool_calls is not None
            assert len(response.tool_calls) == 1
            assert response.tool_calls[0].function.name == "calculate"

            # Verify no tool execution occurred (only 3 messages)
            assert len(agent.messages) == 3  # System, User, Assistant with tool call
            # No tool message should be present


@pytest.mark.asyncio
async def test_call_handles_multiple_tool_calls():
    """Test that call() handles multiple tool calls in sequence."""
    agent_context = await create_test_agent()
    async with agent_context as agent:
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
        calc_call.function.arguments = json.dumps({"expression": "20 * 1.8 + 32"})

        # Mock responses
        responses = [
            # First call requests both tools
            MockLLMResponse(
                "I'll check the weather and convert the temperature.",
                tool_calls=[weather_call, calc_call],
            ),
            # Final response after tool executions
            MockLLMResponse(
                "The weather in Paris is sunny and 72°F, which is about 22°C."
            ),
        ]

        with patch.object(agent.model, "complete", AsyncMock(side_effect=responses)):
            response = await agent.call(
                "What's the weather in Paris and what's that in Celsius?"
            )

            # Verify final response
            assert isinstance(response, AssistantMessage)
            assert "22°C" in response.content or "Paris" in response.content
            assert response.tool_calls is None

            # Verify all messages are present
            # System, User, Assistant with tools, Tool1, Tool2, Final Assistant
            assert len(agent.messages) >= 5


@pytest.mark.asyncio
async def test_call_without_tools_returns_immediately():
    """Test that call() returns immediately when no tools are involved."""
    # Create agent without tools
    async with Agent("You are a helpful assistant.") as agent:
        mock_response = MockLLMResponse(
            "Hello! I'm here to help you with any questions you might have."
        )

        with patch.object(
            agent.model, "complete", AsyncMock(return_value=mock_response)
        ):
            response = await agent.call("Hello!")

            # Verify we got a direct response
            assert isinstance(response, AssistantMessage)
            assert "help" in response.content.lower()
            assert response.tool_calls is None

            # Only 3 messages: System, User, Assistant
            assert len(agent.messages) == 3


@pytest.mark.asyncio
async def test_call_respects_max_iterations():
    """Test that call() respects max_iterations when tools keep being called."""
    agent_context = await create_test_agent()
    async with agent_context as agent:
        # Create a tool call that would repeat
        mock_tool_call = MagicMock()
        mock_tool_call.id = "call_loop"
        mock_tool_call.type = "function"
        mock_tool_call.function.name = "get_weather"
        mock_tool_call.function.arguments = json.dumps({"location": "Tokyo"})

        # Mock responses that always return tool calls (simulating a loop)
        always_tools_response = MockLLMResponse(
            "Checking...", tool_calls=[mock_tool_call]
        )

        call_count = 0

        async def mock_complete(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return always_tools_response

        with patch.object(agent.model, "complete", mock_complete):
            # Even though the LLM keeps returning tool calls, execute should stop
            # after max_iterations (default 10)
            response = await agent.call("Weather in Tokyo?", max_iterations=3)

            # Should have made 3 LLM calls (hitting the limit)
            assert call_count == 3

            # The last message should still be returned
            assert isinstance(response, AssistantMessage)
