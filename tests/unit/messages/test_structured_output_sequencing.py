import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from litellm.types.utils import Choices
from litellm.utils import Message as LiteLLMMessage
from pydantic import BaseModel

from good_agent import Agent
from good_agent.messages import AssistantMessageStructuredOutput, UserMessage
from good_agent.tools import ToolCall, ToolCallFunction


class MockLLMResponse:
    """Mock response from litellm for structured output"""

    def __init__(self, content="Test response", tool_calls=None, usage=None):
        message = LiteLLMMessage()
        message.content = content
        message.tool_calls = tool_calls or []

        choice = Choices()
        choice.message = message
        choice.provider_specific_fields = {}

        self.choices = [choice]
        if usage:
            self.usage = usage


class TestStructuredOutputSequencing:
    """Test that AssistantMessageStructuredOutput is properly handled in message sequencing"""

    @pytest.mark.asyncio
    async def test_ensure_tool_pairs_called_correctly(self):
        """Test that _ensure_tool_call_pairs is actually called and works"""

        class Weather(BaseModel):
            location: str
            temperature: float
            condition: str

        async with Agent("You are helpful") as agent:
            # Manually create an AssistantMessageStructuredOutput
            weather_output = Weather(
                location="New York", temperature=72.0, condition="Sunny"
            )
            tool_call = ToolCall(
                id="call_weather_123",
                type="function",
                function=ToolCallFunction(
                    name="Weather", arguments=json.dumps(weather_output.model_dump())
                ),
            )

            structured_msg = AssistantMessageStructuredOutput[Weather](
                "Weather retrieved", output=weather_output, tool_calls=[tool_call]
            )

            # Add messages to agent history
            agent.messages.append(UserMessage("What's the weather?"))
            agent.messages.append(structured_msg)
            agent.messages.append(UserMessage("Is that typical?"))

            # Format messages (this is what agent.call does before calling complete)
            formatted = await agent.model.format_message_list_for_llm(agent.messages)

            print("\n=== Before _ensure_tool_call_pairs ===")
            for i, msg in enumerate(formatted):
                role = (
                    msg.get("role")
                    if isinstance(msg, dict)
                    else getattr(msg, "role", None)
                )
                tool_calls = (
                    msg.get("tool_calls")
                    if isinstance(msg, dict)
                    else getattr(msg, "tool_calls", None)
                )
                print(f"{i}: role={role}, has_tool_calls={bool(tool_calls)}")

            # Now call _ensure_tool_call_pairs (this is what complete() does)
            with_pairs = agent.model._ensure_tool_call_pairs_for_formatted_messages(
                formatted
            )

            print("\n=== After _ensure_tool_call_pairs ===")
            for i, msg in enumerate(with_pairs):
                role = (
                    msg.get("role")
                    if isinstance(msg, dict)
                    else getattr(msg, "role", None)
                )
                tool_call_id = (
                    msg.get("tool_call_id")
                    if isinstance(msg, dict)
                    else getattr(msg, "tool_call_id", None)
                )
                print(f"{i}: role={role}, tool_call_id={tool_call_id}")

            # Find assistant with tool_calls
            assistant_idx = None
            for i, msg in enumerate(with_pairs):
                role = (
                    msg.get("role")
                    if isinstance(msg, dict)
                    else getattr(msg, "role", None)
                )
                tool_calls = (
                    msg.get("tool_calls")
                    if isinstance(msg, dict)
                    else getattr(msg, "tool_calls", None)
                )
                if role == "assistant" and tool_calls:
                    assistant_idx = i
                    break

            assert assistant_idx is not None
            # Check if synthetic tool response was injected
            next_msg = with_pairs[assistant_idx + 1]
            next_role = (
                next_msg.get("role")
                if isinstance(next_msg, dict)
                else getattr(next_msg, "role", None)
            )
            assert next_role == "tool", (
                f"Expected synthetic tool response after assistant, got {next_role}"
            )

    @pytest.mark.asyncio
    async def test_structured_output_followed_by_regular_call_real(self):
        """Test the real scenario: response_model call followed by regular call"""

        class Weather(BaseModel):
            location: str
            temperature: float
            condition: str

        async with Agent("You are a test agent") as agent:
            # Mock the extract and complete methods
            mock_weather = Weather(
                location="New York", temperature=72.0, condition="Sunny"
            )

            # Create tool call that would be on the structured output response
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_weather_123"
            mock_tool_call.type = "function"
            mock_tool_call.function = MagicMock()
            mock_tool_call.function.name = "Weather"
            mock_tool_call.function.arguments = json.dumps(mock_weather.model_dump())

            # Mock the response from extract (with tool calls)
            mock_structured_response = MockLLMResponse(
                content="Weather data retrieved",
                tool_calls=[mock_tool_call],
                usage=MagicMock(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
            )

            # Mock the response for the second regular call
            mock_regular_response = MockLLMResponse(
                content="Yes, that's typical for this time of year",
                usage=MagicMock(
                    prompt_tokens=15, completion_tokens=25, total_tokens=40
                ),
            )

            # Set up mocks
            agent.model.api_responses = [mock_structured_response]
            agent.model.api_requests = [{}]

            with patch.object(
                agent.model, "extract", AsyncMock(return_value=mock_weather)
            ):
                # First call with response_model - creates AssistantMessageStructuredOutput
                weather = await agent.call(
                    "What's the weather in New York?", response_model=Weather
                )

                assert isinstance(weather, AssistantMessageStructuredOutput)
                assert weather.output.location == "New York"

                # Now make a second regular call - this is where the bug happens
                # The agent history has AssistantMessageStructuredOutput with tool_calls
                # but no ToolMessage responses. The validation and formatting should handle this.
                with patch.object(
                    agent.model,
                    "complete",
                    AsyncMock(return_value=mock_regular_response),
                ) as mock_complete:
                    response = await agent.call(
                        "Is that typical for this time of year?"
                    )

                    # The call should succeed
                    assert (
                        response.content == "Yes, that's typical for this time of year"
                    )

                    # Verify that complete was called with properly formatted messages
                    # that include synthetic tool responses
                    assert mock_complete.called
                    call_args = mock_complete.call_args
                    formatted_messages = call_args[0][0]

                    # Find the assistant message with tool calls (from first structured output call)
                    assistant_idx = None
                    for i, msg in enumerate(formatted_messages):
                        role = (
                            msg.get("role")
                            if isinstance(msg, dict)
                            else getattr(msg, "role", None)
                        )
                        tool_calls = (
                            msg.get("tool_calls")
                            if isinstance(msg, dict)
                            else getattr(msg, "tool_calls", None)
                        )
                        if role == "assistant" and tool_calls:
                            assistant_idx = i
                            break

                    # THIS IS THE KEY ASSERTION - synthetic tool response should be injected
                    assert assistant_idx is not None, (
                        "Should have assistant message with tool calls"
                    )
                    tool_response = formatted_messages[assistant_idx + 1]
                    role = (
                        tool_response.get("role")
                        if isinstance(tool_response, dict)
                        else getattr(tool_response, "role", None)
                    )
                    assert role == "tool", (
                        f"Expected tool response after assistant, got {role}"
                    )

    @pytest.mark.asyncio
    async def test_structured_output_creates_assistant_message(self):
        """Test that response_model creates AssistantMessageStructuredOutput"""

        class SearchResult(BaseModel):
            query: str
            results: list[str]
            count: int

        async with Agent("You are helpful") as agent:
            # Mock the extract method to return structured output
            mock_output = SearchResult(
                query="python tutorials",
                results=["Tutorial 1", "Tutorial 2"],
                count=2,
            )

            # Create a mock tool call that represents the structured output
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_structured_123"
            mock_tool_call.type = "function"
            mock_tool_call.function = MagicMock()
            mock_tool_call.function.name = "SearchResult"
            mock_tool_call.function.arguments = json.dumps(mock_output.model_dump())

            mock_response = MockLLMResponse(
                content="Found results",
                tool_calls=[mock_tool_call],
                usage=MagicMock(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
            )

            # Set api_responses and api_requests manually - extract method accesses both
            agent.model.api_responses = [mock_response]
            agent.model.api_requests = [{}]  # Dummy request

            with patch.object(
                agent.model, "extract", AsyncMock(return_value=mock_output)
            ):
                # Make call with response_model
                response = await agent.call(
                    "Search for python tutorials", response_model=SearchResult
                )

                # Verify response is AssistantMessageStructuredOutput
                assert isinstance(response, AssistantMessageStructuredOutput)
                assert response.output == mock_output
                assert response.output.query == "python tutorials"
                assert response.output.count == 2

    @pytest.mark.asyncio
    async def test_structured_output_followed_by_regular_call(self):
        """Test that subsequent calls after structured output maintain valid message sequence"""

        class WeatherData(BaseModel):
            location: str
            temperature: int
            condition: str

        async with Agent("You are helpful") as agent:
            # First call with structured output
            mock_weather = WeatherData(
                location="Paris", temperature=72, condition="Sunny"
            )

            # Mock tool call for structured output
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_weather_123"
            mock_tool_call.type = "function"
            mock_tool_call.function = MagicMock()
            mock_tool_call.function.name = "WeatherData"
            mock_tool_call.function.arguments = json.dumps(mock_weather.model_dump())

            mock_structured_response = MockLLMResponse(
                content="Weather data retrieved",
                tool_calls=[mock_tool_call],
                usage=MagicMock(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
            )

            # Mock the second regular response
            mock_regular_response = MockLLMResponse(
                content="The weather looks great!",
                usage=MagicMock(
                    prompt_tokens=15, completion_tokens=25, total_tokens=40
                ),
            )

            # Set api_responses and api_requests manually - extract method accesses both
            agent.model.api_responses = [mock_structured_response]
            agent.model.api_requests = [{}]

            with patch.object(
                agent.model, "extract", AsyncMock(return_value=mock_weather)
            ):
                # First call with structured output
                response1 = await agent.call(
                    "What's the weather in Paris?", response_model=WeatherData
                )

                assert isinstance(response1, AssistantMessageStructuredOutput)
                assert response1.output.location == "Paris"

                # Second regular call - this should trigger message formatting
                # that properly handles the AssistantMessageStructuredOutput
                with patch.object(
                    agent.model,
                    "complete",
                    AsyncMock(return_value=mock_regular_response),
                ) as mock_complete:
                    response2 = await agent.call("That sounds nice!")

                    # Verify second response
                    assert response2.content == "The weather looks great!"

                    # Verify complete was called with properly formatted messages
                    assert mock_complete.called
                    call_args = mock_complete.call_args
                    formatted_messages = call_args[0][0]

                    # The formatted messages should have proper sequencing
                    # Should include synthetic tool responses for structured output
                    assert len(formatted_messages) > 0

    @pytest.mark.asyncio
    async def test_ensure_tool_call_pairs_handles_structured_output(self):
        """Test that _ensure_tool_call_pairs_for_formatted_messages handles structured outputs"""

        async with Agent("You are helpful") as agent:
            # Create a mock assistant message with tool calls (simulating structured output)
            mock_tool_call = {
                "id": "call_data_123",
                "type": "function",
                "function": {
                    "name": "DataModel",
                    "arguments": '{"value":"test","count":5}',
                },
            }

            # Simulate formatted messages with assistant message containing tool calls
            formatted_messages = [
                {"role": "user", "content": "Get data"},
                {
                    "role": "assistant",
                    "content": "Data retrieved",
                    "tool_calls": [mock_tool_call],
                },
                # No tool response following - this is the case we want to handle
                {"role": "user", "content": "Thanks!"},
            ]

            # Call the method that should insert synthetic tool responses
            result = agent.model._ensure_tool_call_pairs_for_formatted_messages(
                formatted_messages
            )

            # Verify synthetic tool response was inserted
            assert len(result) == 4  # user + assistant + synthetic_tool + user

            # Find the assistant message with tool calls
            assistant_idx = None
            for i, msg in enumerate(result):
                if msg.get("role") == "assistant" and msg.get("tool_calls") is not None:
                    assistant_idx = i
                    break

            assert assistant_idx is not None

            # Verify tool response immediately follows assistant
            tool_response = result[assistant_idx + 1]
            assert tool_response["role"] == "tool"
            assert tool_response["tool_call_id"] == "call_data_123"
            # Synthetic tool responses have empty content "{}"
            assert tool_response["content"] == "{}"

    @pytest.mark.asyncio
    async def test_multiple_structured_outputs_with_regular_calls(self):
        """Test multiple structured output calls interspersed with regular calls"""

        class QueryResult(BaseModel):
            query: str
            found: bool

        async with Agent("You are helpful") as agent:
            mock_result1 = QueryResult(query="first", found=True)
            mock_result2 = QueryResult(query="second", found=False)

            # Mock tool calls for both structured outputs
            mock_tool_call_1 = MagicMock()
            mock_tool_call_1.id = "call_q1"
            mock_tool_call_1.type = "function"
            mock_tool_call_1.function = MagicMock()
            mock_tool_call_1.function.name = "QueryResult"
            mock_tool_call_1.function.arguments = json.dumps(mock_result1.model_dump())

            mock_tool_call_2 = MagicMock()
            mock_tool_call_2.id = "call_q2"
            mock_tool_call_2.type = "function"
            mock_tool_call_2.function = MagicMock()
            mock_tool_call_2.function.name = "QueryResult"
            mock_tool_call_2.function.arguments = json.dumps(mock_result2.model_dump())

            mock_response_1 = MockLLMResponse(
                content="Query executed",
                tool_calls=[mock_tool_call_1],
                usage=MagicMock(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
            )

            mock_response_2 = MockLLMResponse(
                content="Query executed",
                tool_calls=[mock_tool_call_2],
                usage=MagicMock(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
            )

            mock_regular = MockLLMResponse(
                content="Got it",
                usage=MagicMock(prompt_tokens=5, completion_tokens=10, total_tokens=15),
            )

            # Set api_responses and api_requests manually
            agent.model.api_responses = [mock_response_1]
            agent.model.api_requests = [{}]

            with patch.object(
                agent.model,
                "extract",
                AsyncMock(side_effect=[mock_result1, mock_result2]),
            ):
                # First structured output call
                response1 = await agent.call("First query", response_model=QueryResult)
                assert isinstance(response1, AssistantMessageStructuredOutput)
                assert response1.output.query == "first"

                # Regular call
                with patch.object(
                    agent.model, "complete", AsyncMock(return_value=mock_regular)
                ):
                    response2 = await agent.call("Continue")
                    assert response2.content == "Got it"

                # Update api_responses and api_requests for second structured output call
                agent.model.api_responses.append(mock_response_2)
                agent.model.api_requests.append({})

                # Second structured output call
                response3 = await agent.call("Second query", response_model=QueryResult)
                assert isinstance(response3, AssistantMessageStructuredOutput)
                assert response3.output.query == "second"

                # Verify all messages are in the conversation
                messages = agent.messages
                structured_outputs = [
                    m
                    for m in messages
                    if isinstance(m, AssistantMessageStructuredOutput)
                ]
                assert len(structured_outputs) == 2

    @pytest.mark.asyncio
    async def test_structured_output_message_validation(self):
        """Test that message sequence validation properly handles structured outputs"""

        class Config(BaseModel):
            setting: str
            enabled: bool

        async with Agent("You are helpful") as agent:
            mock_config = Config(setting="test", enabled=True)

            # Mock tool call
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_config_123"
            mock_tool_call.type = "function"
            mock_tool_call.function = MagicMock()
            mock_tool_call.function.name = "Config"
            mock_tool_call.function.arguments = json.dumps(mock_config.model_dump())

            mock_response = MockLLMResponse(
                content="Configuration set",
                tool_calls=[mock_tool_call],
                usage=MagicMock(
                    prompt_tokens=10, completion_tokens=20, total_tokens=30
                ),
            )

            # Set api_responses and api_requests manually
            agent.model.api_responses = [mock_response]
            agent.model.api_requests = [{}]

            with patch.object(
                agent.model, "extract", AsyncMock(return_value=mock_config)
            ):
                # This should not raise validation errors
                response = await agent.call("Set configuration", response_model=Config)

                assert isinstance(response, AssistantMessageStructuredOutput)

                # The message should be in the agent's message list
                assert response in agent.messages

                # Message sequence should be valid for subsequent calls
                # The validation happens during format_message_list_for_llm
                formatted = await agent.model.format_message_list_for_llm(
                    agent.messages
                )

                # Should not raise any validation errors
                assert len(formatted) > 0
