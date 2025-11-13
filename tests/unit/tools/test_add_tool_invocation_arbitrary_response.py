from typing import Any

import pytest
from pydantic import BaseModel

from good_agent import Agent
from good_agent.tools import ToolResponse, tool


class CustomResponse(BaseModel):
    """Custom response type for testing."""

    status: str
    data: dict[str, Any]
    metadata: dict[str, Any] | None = None


class TestAddToolInvocationArbitraryResponse:
    """Test add_tool_invocation with various response types."""

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_tool_response(self):
        """Test add_tool_invocation with standard ToolResponse."""
        agent = Agent("Test agent")
        await agent.ready()  # Ensure agent is ready

        # Create a standard ToolResponse
        response = ToolResponse(
            tool_name="search",
            response="Search results",
            parameters={"query": "test"},
            success=True,
        )

        # Add tool invocation
        agent.add_tool_invocation(
            tool="search", response=response, parameters={"query": "test"}
        )

        # Verify messages were added
        assert (
            len(agent.messages) == 3
        )  # system, assistant with tool call, tool response

        # Check assistant message
        assistant_msg = agent.assistant[-1]
        assert assistant_msg.tool_calls is not None
        assert len(assistant_msg.tool_calls) == 1
        assert assistant_msg.tool_calls[0].function.name == "search"

        # Check tool message
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "search"
        assert "Search results" in tool_msg.content
        assert tool_msg.tool_response and tool_msg.tool_response.success is True

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_string_response(self):
        """Test add_tool_invocation with a simple string response."""
        agent = Agent("Test agent")

        # Add tool invocation with string response
        agent.add_tool_invocation(
            tool="calculator",
            response="42",  # Simple string response
            parameters={"expression": "40 + 2"},
        )

        # Verify messages were added
        assert len(agent.messages) == 3

        # Check that ToolResponse was created automatically
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "calculator"
        assert "42" in tool_msg.content
        assert tool_msg.tool_response and tool_msg.tool_response.response == "42"
        assert tool_msg.tool_response and tool_msg.tool_response.success is True
        assert tool_msg.tool_response and tool_msg.tool_response.error is None

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_dict_response(self):
        """Test add_tool_invocation with a dictionary response."""
        agent = Agent("Test agent")

        # Add tool invocation with dict response
        response_data = {"results": ["item1", "item2", "item3"], "total": 3, "page": 1}

        agent.add_tool_invocation(
            tool="list_items",
            response=response_data,  # Dict response
            parameters={"page": 1, "limit": 10},
        )

        # Verify ToolResponse was created with dict
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "list_items"
        assert (
            tool_msg.tool_response and tool_msg.tool_response.response == response_data
        )
        assert tool_msg.tool_response and tool_msg.tool_response.success is True

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_pydantic_model_response(self):
        """Test add_tool_invocation with a Pydantic model response."""
        agent = Agent("Test agent")
        await agent.ready()  # Ensure agent is ready

        # Create custom response object
        custom_response = CustomResponse(
            status="success",
            data={"count": 5, "items": ["a", "b", "c", "d", "e"]},
            metadata={"timestamp": "2025-01-13T10:00:00Z"},
        )

        agent.add_tool_invocation(
            tool="fetch_data",
            response=custom_response,  # Pydantic model response
            parameters={"source": "database"},
        )

        # Verify ToolResponse was created with model
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "fetch_data"
        assert tool_msg.tool_response.response == custom_response
        assert tool_msg.tool_response.success is True

        # Verify content shows the model correctly
        assert (
            str(custom_response) in tool_msg.content
            or "CustomResponse" in tool_msg.content
        )

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_list_response(self):
        """Test add_tool_invocation with a list response."""
        agent = Agent("Test agent")

        # Add tool invocation with list response
        response_list = [1, 2, 3, 4, 5]

        agent.add_tool_invocation(
            tool="get_numbers", response=response_list, parameters={"count": 5}
        )

        # Verify ToolResponse was created with list
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "get_numbers"
        assert tool_msg.tool_response.response == response_list
        assert "[1, 2, 3, 4, 5]" in tool_msg.content

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_none_response(self):
        """Test add_tool_invocation with None response."""
        agent = Agent("Test agent")

        # Add tool invocation with None response
        agent.add_tool_invocation(
            tool="void_function", response=None, parameters={"action": "delete"}
        )

        # Verify ToolResponse was created with None
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "void_function"
        assert tool_msg.tool_response.response is None
        assert tool_msg.tool_response.success is True
        assert "None" in tool_msg.content

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_tool_instance(self):
        """Test add_tool_invocation with Tool instance."""

        @tool
        def my_tool(input: str) -> str:
            """Process input."""
            return f"Processed: {input}"

        agent = Agent("Test agent")

        # Add tool invocation with Tool instance
        agent.add_tool_invocation(
            tool=my_tool,  # Tool instance
            response="Processed: test",
            parameters={"input": "test"},
        )

        # Verify correct tool name was used
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "my_tool"
        assert "Processed: test" in tool_msg.content

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_callable(self):
        """Test add_tool_invocation with regular callable."""

        def regular_function(x: int) -> int:
            """Double the input."""
            return x * 2

        agent = Agent("Test agent")

        # Add tool invocation with callable
        agent.add_tool_invocation(
            tool=regular_function,  # Regular callable
            response=10,
            parameters={"x": 5},
        )

        # Verify function name was used
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "regular_function"
        assert "10" in tool_msg.content

    @pytest.mark.asyncio
    async def test_add_tool_invocation_skip_assistant_message(self):
        """Test add_tool_invocation with skip_assistant_message=True."""
        agent = Agent("Test agent")

        # First add an assistant message with tool call manually
        from good_agent.messages import AssistantMessage
        from good_agent.tools import ToolCall, ToolCallFunction

        tool_call = ToolCall(
            id="test_call_123",
            type="function",
            function=ToolCallFunction(name="test_tool", arguments='{"param": "value"}'),
        )

        assistant_msg = AssistantMessage(tool_calls=[tool_call])
        agent.append(assistant_msg)

        # Now add tool invocation, skipping assistant message
        agent.add_tool_invocation(
            tool="test_tool",
            response="Tool executed successfully",
            parameters={"param": "value"},
            tool_call_id="test_call_123",
            skip_assistant_message=True,
        )

        # Verify only one assistant message exists
        assert len(agent.assistant) == 1
        # Verify tool message was added
        assert len(agent.tool) == 1
        assert agent.tool[-1].tool_call_id == "test_call_123"

    @pytest.mark.asyncio
    async def test_add_tool_invocation_preserves_tool_response_fields(self):
        """Test that existing ToolResponse fields are preserved."""
        agent = Agent("Test agent")

        # Create ToolResponse with all fields
        original_response = ToolResponse(
            tool_name="original_tool",
            tool_call_id="original_id",
            response={"data": "test"},
            parameters={"original": "params"},
            success=False,
            error="Original error",
        )

        # Add with override tool name but preserve other fields
        agent.add_tool_invocation(
            tool="override_tool",  # This should override tool_name
            response=original_response,
            tool_call_id="new_id",  # This should override tool_call_id
        )

        # Verify fields were properly handled
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_name == "override_tool"  # Overridden
        assert tool_msg.tool_call_id == "new_id"  # Overridden
        assert tool_msg.tool_response.response == {"data": "test"}  # Preserved
        assert tool_msg.tool_response.success is False  # Preserved
        assert tool_msg.tool_response.error == "Original error"  # Preserved
        assert "Error: Original error" in tool_msg.content  # Error format preserved

    @pytest.mark.asyncio
    async def test_add_tool_invocation_with_complex_object(self):
        """Test add_tool_invocation with complex nested objects."""
        agent = Agent("Test agent")

        # Complex nested response
        complex_response = {
            "user": {
                "id": 123,
                "name": "Test User",
                "preferences": {"theme": "dark", "notifications": True},
            },
            "data": [{"id": 1, "value": "a"}, {"id": 2, "value": "b"}],
            "metadata": {"timestamp": 1234567890, "version": "1.0.0"},
        }

        agent.add_tool_invocation(
            tool="get_user_data", response=complex_response, parameters={"user_id": 123}
        )

        # Verify complex object was stored correctly
        tool_msg = agent.tool[-1]
        assert tool_msg.tool_response.response == complex_response
        assert tool_msg.tool_response.success is True

        # Verify string representation includes the data
        content_str = str(tool_msg.content)
        assert "user" in content_str or str(complex_response) in content_str
