import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage, ToolMessage
from good_agent.tools import ToolResponse, tool


class TestAddToolInvocations:
    """Test the agent.add_tool_invocations() method"""

    @pytest.mark.asyncio
    async def test_add_tool_invocations_with_parallel_support(self, monkeypatch):
        """Test that invocations are consolidated when model supports parallel calls"""

        @tool
        def calculator(operation: str, a: float, b: float) -> float:
            """Perform math operations"""
            if operation == "add":
                return a + b
            elif operation == "multiply":
                return a * b
            return 0.0

        async with Agent("Test agent", model="gpt-4", tools=[calculator]) as agent:
            # Mock the model to support parallel function calling
            monkeypatch.setattr(agent.model, "supports_parallel_function_calling", lambda: True)

            initial_len = len(agent)

            # Prepare multiple invocations
            invocations = [
                ({"operation": "add", "a": 2, "b": 3}, 5.0),
                ({"operation": "multiply", "a": 4, "b": 5}, 20.0),
                ({"operation": "add", "a": 10, "b": 15}, 25.0),
            ]

            # Add multiple invocations
            agent.add_tool_invocations(calculator, invocations)

            # Should have added 1 assistant message + 3 tool messages = 4 total
            assert len(agent) == initial_len + 4

            # Check the assistant message has all tool calls
            # The assistant message is the first one added after the system message
            assistant_msg = agent.messages[initial_len]
            assert isinstance(assistant_msg, AssistantMessage)
            assert assistant_msg.tool_calls is not None
            assert len(assistant_msg.tool_calls) == 3
            assert assistant_msg.tool_calls[0].function.name == "calculator"
            assert assistant_msg.tool_calls[1].function.name == "calculator"
            assert assistant_msg.tool_calls[2].function.name == "calculator"

            # Check tool response messages
            for i in range(3):
                tool_msg = agent.messages[initial_len + 1 + i]
                assert isinstance(tool_msg, ToolMessage)
                assert tool_msg.tool_name == "calculator"
                # Check the response matches what we provided
                expected_response = invocations[i][1]
                assert tool_msg.content == str(expected_response)

    @pytest.mark.asyncio
    async def test_add_tool_invocations_without_parallel_support(self, monkeypatch):
        """Test that invocations fall back to individual messages when model doesn't support parallel calls"""

        @tool
        def simple_tool(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[simple_tool]) as agent:
            # Mock the model to NOT support parallel function calling
            monkeypatch.setattr(agent.model, "supports_parallel_function_calling", lambda: False)

            initial_len = len(agent)

            # Prepare multiple invocations
            invocations = [
                ({"x": 1}, 2),
                ({"x": 5}, 10),
            ]

            # Add multiple invocations
            agent.add_tool_invocations(simple_tool, invocations)

            # Without parallel support, should add 2 assistant messages + 2 tool messages = 4 total
            # Each tool call gets its own assistant message when parallel is not supported
            assert len(agent) == initial_len + 4

            # Check first invocation pair
            first_assistant = agent.messages[initial_len]
            assert isinstance(first_assistant, AssistantMessage)
            tool_calls = first_assistant.tool_calls
            assert tool_calls is not None
            assert len(tool_calls) == 1
            first_tool = agent.messages[initial_len + 1]
            assert isinstance(first_tool, ToolMessage)
            assert first_tool.content == "2"

            # Check second invocation pair
            second_assistant = agent.messages[initial_len + 2]
            assert isinstance(second_assistant, AssistantMessage)
            second_tool_calls = second_assistant.tool_calls
            assert second_tool_calls is not None
            assert len(second_tool_calls) == 1
            second_tool = agent.messages[initial_len + 3]
            assert isinstance(second_tool, ToolMessage)
            assert second_tool.content == "10"

    @pytest.mark.asyncio
    async def test_add_tool_invocations_skip_assistant_message(self, monkeypatch):
        """Test skip_assistant_message parameter"""

        @tool
        def echo(message: str) -> str:
            return f"Echo: {message}"

        async with Agent("Test agent", tools=[echo]) as agent:
            # Mock to support parallel calls
            monkeypatch.setattr(agent.model, "supports_parallel_function_calling", lambda: True)

            # First add a user message
            agent.append("Please echo some messages")

            # Manually add an assistant message with tool calls
            import json

            from good_agent.messages import AssistantMessage
            from good_agent.tools import ToolCall, ToolCallFunction

            tool_calls = [
                ToolCall(
                    id="manual_1",
                    type="function",
                    function=ToolCallFunction(
                        name="echo", arguments=json.dumps({"message": "Hello"})
                    ),
                ),
                ToolCall(
                    id="manual_2",
                    type="function",
                    function=ToolCallFunction(
                        name="echo", arguments=json.dumps({"message": "World"})
                    ),
                ),
            ]

            agent.append(AssistantMessage(content="I'll echo those", tool_calls=tool_calls))

            initial_len = len(agent)

            # Now add tool responses without creating new assistant message
            invocations = [
                ({"message": "Hello"}, "Echo: Hello"),
                ({"message": "World"}, "Echo: World"),
            ]

            agent.add_tool_invocations(echo, invocations, skip_assistant_message=True)

            # Should only add tool response messages (2 messages)
            assert len(agent) == initial_len + 2

            # Both should be tool messages
            assert isinstance(agent.messages[initial_len], ToolMessage)
            assert agent.messages[initial_len].content == "Echo: Hello"
            assert isinstance(agent.messages[initial_len + 1], ToolMessage)
            assert agent.messages[initial_len + 1].content == "Echo: World"

    @pytest.mark.asyncio
    async def test_add_tool_invocations_with_tool_response_objects(self, monkeypatch):
        """Test that ToolResponse objects are handled correctly"""

        @tool
        def process(data: str) -> str:
            return f"Processed: {data}"

        async with Agent("Test agent", tools=[process]) as agent:
            monkeypatch.setattr(agent.model, "supports_parallel_function_calling", lambda: True)

            initial_len = len(agent)

            # Use ToolResponse objects instead of raw values
            invocations = [
                (
                    {"data": "input1"},
                    ToolResponse(
                        tool_name="process",
                        tool_call_id="custom_1",
                        response="Processed: input1",
                        parameters={"data": "input1"},
                        success=True,
                        error=None,
                    ),
                ),
                (
                    {"data": "input2"},
                    ToolResponse(
                        tool_name="process",
                        tool_call_id="custom_2",
                        response=None,
                        parameters={"data": "input2"},
                        success=False,
                        error="Failed to process",
                    ),
                ),
            ]

            agent.add_tool_invocations(process, invocations)

            # Check messages were added correctly
            assert len(agent) == initial_len + 3  # 1 assistant + 2 tool messages

            # Check successful response
            success_msg = agent.messages[initial_len + 1]
            assert isinstance(success_msg, ToolMessage)
            assert success_msg.content == "Processed: input1"
            assert success_msg.tool_response is not None
            assert success_msg.tool_response.success is True

            # Check error response
            error_msg = agent.messages[initial_len + 2]
            assert isinstance(error_msg, ToolMessage)
            assert error_msg.content == "Error: Failed to process"
            assert error_msg.tool_response is not None
            assert error_msg.tool_response.success is False

    @pytest.mark.asyncio
    async def test_add_tool_invocations_empty_list(self):
        """Test that empty invocations list is handled gracefully"""

        @tool
        def dummy_tool() -> str:
            return "dummy"

        async with Agent("Test agent", tools=[dummy_tool]) as agent:
            initial_len = len(agent)

            # Add empty invocations
            agent.add_tool_invocations(dummy_tool, [])

            # No messages should be added
            assert len(agent) == initial_len

    @pytest.mark.asyncio
    async def test_add_tool_invocations_with_string_tool_name(self, monkeypatch):
        """Test using tool name as string"""

        @tool
        def named_tool(value: int) -> int:
            return value + 1

        async with Agent("Test agent", tools=[named_tool]) as agent:
            monkeypatch.setattr(agent.model, "supports_parallel_function_calling", lambda: True)

            initial_len = len(agent)

            invocations = [
                ({"value": 1}, 2),
                ({"value": 5}, 6),
            ]

            # Use tool name as string instead of the tool object
            agent.add_tool_invocations("named_tool", invocations)

            # Should work the same way
            assert len(agent) == initial_len + 3  # 1 assistant + 2 tool messages
            assistant_msg = agent.messages[initial_len]
            assert isinstance(assistant_msg, AssistantMessage)
            tool_calls = assistant_msg.tool_calls
            assert tool_calls is not None
            assert len(tool_calls) == 2
