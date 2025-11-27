import asyncio
import json
from typing import Any, cast

import pytest
from good_agent import Agent
from good_agent.messages import AssistantMessage, ToolCall, ToolMessage
from good_agent.tools import ToolCallFunction, ToolContext, ToolResponse, tool

# invoke functionality is now implemented - tests should pass


class TestAgentInvoke:
    """Test the agent.invoke() method"""

    @pytest.mark.asyncio
    async def test_basic_invoke(self):
        """Test basic tool invocation"""

        @tool
        async def calculate(operation: str, a: float, b: float) -> float:
            """Perform basic math operations"""
            if operation == "add":
                return a + b
            elif operation == "multiply":
                return a * b
            else:
                raise ValueError(f"Unknown operation: {operation}")

        async with Agent("You are a helpful assistant.", tools=[calculate]) as agent:
            initial_len = len(agent)  # Just system message

            # Directly invoke the tool - this will CREATE an assistant message
            result = await agent.invoke(calculate, operation="add", a=5, b=3)

            assert result.success is True
            assert result.response == 8
            assert result.tool_name == "calculate"
            assert result.parameters == {"operation": "add", "a": 5, "b": 3}

            # Check message history - invoke added 2 messages
            assert len(agent) == initial_len + 2

            # Assistant message was created by invoke
            assistant_msg = agent[-2]
            assert isinstance(assistant_msg, AssistantMessage)
            assert (
                assistant_msg.content == ""
            )  # Tool calls typically have empty content
            tool_calls = assistant_msg.tool_calls
            assert tool_calls is not None
            assert len(tool_calls) == 1
            assert tool_calls[0].function.name == "calculate"
            assert json.loads(tool_calls[0].function.arguments) == {
                "operation": "add",
                "a": 5,
                "b": 3,
            }

            # Tool response message
            tool_msg = agent[-1]
            assert isinstance(tool_msg, ToolMessage)
            assert tool_msg.content == "8.0"
            assert tool_msg.tool_response == result

    @pytest.mark.asyncio
    async def test_invoke_with_custom_tool_call_id(self):
        """Test invoke with custom tool call ID"""

        @tool
        async def simple_tool_custom_id(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[simple_tool_custom_id]) as agent:
            result = await agent.invoke(
                simple_tool_custom_id, tool_call_id="custom_id_123", x=10
            )

            assert result.tool_call_id == "custom_id_123"
            tool_msg = agent[-1]
            assert isinstance(tool_msg, ToolMessage)
            assert tool_msg.tool_call_id == "custom_id_123"
            assistant_msg = agent[-2]
            assert isinstance(assistant_msg, AssistantMessage)
            tool_calls = assistant_msg.tool_calls
            assert tool_calls is not None
            assert tool_calls[0].id == "custom_id_123"

    @pytest.mark.asyncio
    async def test_invoke_skip_assistant_message(self):
        """Test invoke with skip_assistant_message=True"""

        @tool
        async def echo_tool(message: str) -> str:
            return f"Echo: {message}"

        async with Agent("Test agent", tools=[echo_tool]) as agent:
            # Scenario: Processing an LLM tool call
            # First add user message
            agent.append("Echo 'Hello' for me")

            # Simulate LLM response with tool call
            agent.assistant.append(
                "I'll echo that for you.",
                tool_calls=[
                    ToolCall(
                        id="llm_generated_id",
                        type="function",
                        function=ToolCallFunction(
                            name="echo_tool", arguments=json.dumps({"message": "Hello"})
                        ),
                    )
                ],
            )

            # Now process the tool call - skip creating assistant message
            await agent.invoke(
                echo_tool,
                tool_call_id="llm_generated_id",
                skip_assistant_message=True,
                message="Hello",
            )

            # Should have: system, user, assistant (with tool call), tool
            assert len(agent) == 4
            assert agent[0].role == "system"
            assert agent[1].role == "user"
            assert agent[2].role == "assistant"  # The one we added manually
            assistant_msg = agent[2]
            assert isinstance(assistant_msg, AssistantMessage)
            tool_calls = assistant_msg.tool_calls
            assert tool_calls is not None
            assert tool_calls[0].id == "llm_generated_id"
            tool_msg = agent[3]
            assert isinstance(tool_msg, ToolMessage)
            assert tool_msg.content == "Echo: Hello"
            assert tool_msg.tool_call_id == "llm_generated_id"

    @pytest.mark.asyncio
    async def test_invoke_with_error(self):
        """Test tool invocation that raises an error"""

        @tool
        async def risky_tool(x: int) -> int:
            """A tool that might fail"""
            if x < 0:
                raise ValueError("x must be non-negative")
            return x * 2

        async with Agent("Test agent", tools=[risky_tool]) as agent:
            # Successful invocation
            result = await agent.invoke(risky_tool, x=5)
            assert result.success is True
            assert result.response == 10

            # Failed invocation
            result = await agent.invoke(risky_tool, x=-1)
            assert result.success is False
            assert result.error is not None
            assert "x must be non-negative" in result.error
            assert result.response is None

            # Error is recorded in history
            tool_msg = agent[-1]
            assert isinstance(tool_msg, ToolMessage)
            assert "x must be non-negative" in tool_msg.content

    @pytest.mark.asyncio
    async def test_invoke_with_sync_tool(self):
        """Test invoke with synchronous tool"""

        @tool
        def sync_tool(text: str) -> str:
            """A synchronous tool"""
            return text.upper()

        async with Agent("Test agent", tools=[sync_tool]) as agent:
            result = await agent.invoke(sync_tool, text="hello world")

            assert result.success is True
            assert result.response == "HELLO WORLD"
            assert agent[-1].content == "HELLO WORLD"

    @pytest.mark.asyncio
    async def test_invoke_with_tool_context_injection(self):
        """Test invoke with tools that require context injection"""

        @tool
        async def context_aware_tool(query: str, ctx: ToolContext) -> str:
            """A tool that uses context"""
            return f"Agent {ctx.agent.session_id} processing: {query}"

        async with Agent("Test agent", tools=[context_aware_tool]) as agent:
            result = await agent.invoke(
                context_aware_tool, query="test query"
            )

            assert result.success is True
            assert f"Agent {agent.session_id} processing: test query" in result.response

    @pytest.mark.asyncio
    async def test_invoke_with_tool_returning_tool_response(self):
        """Test invoke with tool that returns ToolResponse directly"""

        @tool
        async def smart_tool(value: int) -> ToolResponse:
            """A tool that returns ToolResponse"""
            if value < 0:
                return ToolResponse(
                    tool_name="smart_tool",
                    tool_call_id="",
                    response=None,
                    parameters={"value": value},
                    success=False,
                    error="Value must be non-negative",
                )
            return ToolResponse(
                tool_name="smart_tool",
                tool_call_id="",
                response=value * 3,
                parameters={"value": value},
                success=True,
                error=None,
            )

        async with Agent("Test agent", tools=[smart_tool]) as agent:
            # Successful call
            result = await agent.invoke(smart_tool, value=5)
            assert result.success is True
            assert result.response == 15

            # Failed call
            result = await agent.invoke(smart_tool, value=-1)
            assert result.success is False
            assert result.error == "Value must be non-negative"

    @pytest.mark.asyncio
    async def test_invoke_updates_message_history_correctly(self):
        """Test that invoke properly updates message history"""

        @tool
        async def test_tool(message: str) -> str:
            return f"Processed: {message}"

        async with Agent("Test agent", tools=[test_tool]) as agent:
            initial_len = len(agent)

            # Add a user message to make it more realistic
            agent.append("Please process this message")

            # Invoke creates assistant message THEN tool response
            result = await agent.invoke(test_tool, message="Hello")

            # Should add 2 messages: assistant with tool call, and tool response
            assert len(agent) == initial_len + 3  # user + assistant + tool

            # Verify assistant message was created by invoke
            assistant_msg = agent[-2]
            assert isinstance(assistant_msg, AssistantMessage)
            assert assistant_msg.content == ""  # Tool calls have empty content
            tool_calls = assistant_msg.tool_calls
            assert tool_calls is not None
            assert len(tool_calls) == 1
            assert tool_calls[0].function.name == "test_tool"
            tool_args = json.loads(tool_calls[0].function.arguments)
            assert tool_args == {"message": "Hello"}

            # Verify tool message
            tool_msg = agent[-1]
            assert isinstance(tool_msg, ToolMessage)
            assert tool_msg.content == "Processed: Hello"
            assert tool_msg.tool_response == result

            # Tool call IDs should match
            assert tool_calls[0].id == tool_msg.tool_call_id

    @pytest.mark.asyncio
    async def test_invoke_preserves_tool_metadata(self):
        """Test that invoke preserves tool metadata"""

        async def calc_impl(x: int, y: int) -> int:
            return x + y

        tool_decorator = cast(Any, tool)
        calc = tool_decorator(
            name="custom_calculator", description="A custom calculator tool"
        )(calc_impl)

        async with Agent("Test agent", tools=[calc]) as agent:
            result = await agent.invoke(calc, x=10, y=20)

            assert result.tool_name == "custom_calculator"
            assistant_msg = agent[-2]
            assert isinstance(assistant_msg, AssistantMessage)
            tool_calls = assistant_msg.tool_calls
            assert tool_calls is not None
            assert tool_calls[0].function.name == "custom_calculator"


class TestAgentInvokeFunc:
    """Test the agent.invoke_func() method"""

    @pytest.mark.asyncio
    async def test_basic_invoke_func(self):
        """Test basic bound function creation"""

        @tool
        async def multiply(x: int, y: int) -> int:
            return x * y

        async with Agent("Test agent", tools=[multiply]) as agent:
            # Create bound function
            multiply_by_5 = agent.invoke_func(multiply, y=5)

            # Call it later
            result = await multiply_by_5(x=10)
            assert result.response == 50
            assert result.success is True

    @pytest.mark.asyncio
    async def test_invoke_func_with_partial_params(self):
        """Test invoke_func with partial parameters"""

        @tool
        async def format_message(prefix: str, message: str, suffix: str) -> str:
            return f"{prefix} {message} {suffix}"

        async with Agent("Test agent", tools=[format_message]) as agent:
            # Create bound function with some params preset
            greet = agent.invoke_func(
                format_message, prefix="Hello", suffix="!"
            )

            # Call with remaining param
            result = await greet(message="World")
            assert result.response == "Hello World !"

    @pytest.mark.asyncio
    async def test_invoke_func_with_tool_call_id(self):
        """Test invoke_func with custom tool call ID"""

        @tool
        async def simple_tool_with_id(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[simple_tool_with_id]) as agent:
            bound_func = agent.invoke_func(
                simple_tool_with_id, tool_call_id="preset_id_456"
            )

            result = await bound_func(x=7)
            assert result.tool_call_id == "preset_id_456"
            tool_msg = agent[-1]
            assert isinstance(tool_msg, ToolMessage)
            assert tool_msg.tool_call_id == "preset_id_456"

    @pytest.mark.asyncio
    async def test_invoke_func_type_hints(self):
        """Test that invoke_func preserves type hints"""

        @tool
        async def typed_tool(x: int, y: float) -> str:
            return f"{x} + {y} = {x + y}"

        async with Agent("Test agent", tools=[typed_tool]) as agent:
            bound_func = agent.invoke_func(typed_tool, y=3.14)

            # The bound function should work with proper types
            result = await bound_func(x=10)
            assert result.response == "10 + 3.14 = 13.14"


class TestAgentInvokeMany:
    """Test the agent.invoke_many() method"""

    @pytest.mark.asyncio
    async def test_basic_invoke_many(self):
        """Test basic parallel tool invocation"""

        @tool
        async def add(x: int, y: int) -> int:
            return x + y

        @tool
        async def multiply(x: int, y: int) -> int:
            return x * y

        async with Agent("Test agent", tools=[add, multiply]) as agent:
            results = await agent.invoke_many(
                [(add, {"x": 5, "y": 3}), (multiply, {"x": 4, "y": 7})]
            )

            assert len(results) == 2
            assert results[0].success is True
            assert results[0].response == 8
            assert results[0].tool_name == "add"

            assert results[1].success is True
            assert results[1].response == 28
            assert results[1].tool_name == "multiply"

    @pytest.mark.asyncio
    async def test_invoke_many_with_string_names(self):
        """Test invoke_many with string tool names"""

        @tool
        async def process_data(data: str) -> str:
            return data.upper()

        @tool
        async def count_chars(text: str) -> int:
            return len(text)

        async with Agent("Test agent", tools=[process_data, count_chars]) as agent:
            results = await agent.invoke_many(
                [
                    ("process_data", {"data": "hello world"}),
                    ("count_chars", {"text": "hello world"}),
                ]
            )

            assert len(results) == 2
            assert results[0].success is True
            assert results[0].response == "HELLO WORLD"
            assert results[0].tool_name == "process_data"

            assert results[1].success is True
            assert results[1].response == 11
            assert results[1].tool_name == "count_chars"

    @pytest.mark.asyncio
    async def test_invoke_many_with_failures(self):
        """Test invoke_many with some failing tools"""

        @tool
        async def safe_tool(x: int) -> int:
            return x * 2

        @tool
        async def failing_tool(x: int) -> int:
            raise RuntimeError("This tool always fails")

        async with Agent("Test agent", tools=[safe_tool, failing_tool]) as agent:
            results = await agent.invoke_many(
                [(safe_tool, {"x": 10}), (failing_tool, {"x": 20})]
            )

            assert len(results) == 2
            assert results[0].success is True
            assert results[0].response == 20
            assert results[0].tool_name == "safe_tool"

            assert results[1].success is False
            assert results[1].error is not None
            assert "This tool always fails" in results[1].error
            assert results[1].tool_name == "failing_tool"

    @pytest.mark.asyncio
    async def test_invoke_many_empty(self):
        """Test invoke_many with empty calls"""

        async with Agent("Test agent") as agent:
            results = await agent.invoke_many([])
            assert results == []

    @pytest.mark.asyncio
    async def test_invoke_many_parallel_execution(self):
        """Test that invoke_many executes tools in parallel"""

        execution_times = []

        @tool
        async def slow_tool(name: str, delay: float) -> str:
            start = asyncio.get_event_loop().time()
            await asyncio.sleep(delay)
            end = asyncio.get_event_loop().time()
            execution_times.append((name, start, end))
            return f"Done: {name}"

        async with Agent("Test agent", tools=[slow_tool]) as agent:
            start_time = asyncio.get_event_loop().time()

            results = await agent.invoke_many(
                [
                    (slow_tool, {"name": "first", "delay": 0.1}),
                    (slow_tool, {"name": "second", "delay": 0.1}),
                ]
            )

            end_time = asyncio.get_event_loop().time()
            total_time = end_time - start_time

            # If executed in parallel, should take ~0.1s, not ~0.2s
            assert total_time < 0.15  # Allow some overhead
            assert len(results) == 2
            assert results[0].response == "Done: first"
            assert results[1].response == "Done: second"

    @pytest.mark.asyncio
    async def test_invoke_many_with_mixed_tool_references(self):
        """Test invoke_many with mix of function objects and string names"""

        @tool
        async def tool_a(x: int) -> int:
            return x + 1

        @tool
        async def tool_b(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[tool_a, tool_b]) as agent:
            results = await agent.invoke_many(
                [(tool_a, {"x": 10}), ("tool_b", {"x": 20})]
            )

            assert len(results) == 2
            assert results[0].response == 11
            assert results[0].tool_name == "tool_a"
            assert results[1].response == 40
            assert results[1].tool_name == "tool_b"

    @pytest.mark.asyncio
    async def test_invoke_many_message_history(self):
        """Test that invoke_many updates message history correctly"""

        @tool
        async def tool1(x: int) -> int:
            return x + 1

        @tool
        async def tool2(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[tool1, tool2]) as agent:
            initial_len = len(agent)

            # Add user context
            agent.append("Please run some calculations")

            await agent.invoke_many([(tool1, {"x": 5}), (tool2, {"x": 10})])

            # The exact number of messages depends on whether the model supports
            # multiple tool calls in a single message. It could be either:
            # - 1 assistant message with 2 tool calls + 2 tool responses = 3 messages
            # - 2 assistant messages (1 tool call each) + 2 tool responses = 4 messages
            # Plus the 1 user message we added
            messages_added = len(agent) - initial_len - 1  # Subtract user message
            assert messages_added >= 3  # At minimum: 1 assistant + 2 tools
            assert messages_added <= 4  # At maximum: 2 assistants + 2 tools

            # Verify we have exactly 2 tool responses
            tool_messages = [msg for msg in agent if isinstance(msg, ToolMessage)]
            assert len(tool_messages) == 2

            # Verify tool responses have the correct values
            tool_responses = [
                msg.tool_response.response for msg in tool_messages if msg.tool_response
            ]
            assert 6 in tool_responses  # tool1(5) = 6
            assert 20 in tool_responses  # tool2(10) = 20

    @pytest.mark.asyncio
    async def test_invoke_many_with_nonexistent_tool(self):
        """Test invoke_many with nonexistent tool name"""

        @tool
        async def real_tool(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[real_tool]) as agent:
            results = await agent.invoke_many(
                [
                    (real_tool, {"x": 10}),
                    ("nonexistent_tool", {"x": 20}),
                ]
            )

            assert len(results) == 2
            assert results[0].success is True
            assert results[0].response == 20
            assert results[0].tool_name == "real_tool"

            assert results[1].success is False
            assert results[1].error is not None
            assert "not found" in results[1].error


class TestAgentInvokeManyFunc:
    """Test the agent.invoke_many_func() method"""

    @pytest.mark.asyncio
    async def test_basic_invoke_many_func(self):
        """Test basic bound batch function creation"""

        @tool
        async def calculate(operation: str, a: int, b: int) -> int:
            if operation == "add":
                return a + b
            return a * b

        @tool
        async def format_result(value: int) -> str:
            return f"Result: {value}"

        async with Agent("Test agent", tools=[calculate, format_result]) as agent:
            # Create bound batch function
            calc_batch = agent.invoke_many_func(
                [
                    (calculate, {"operation": "add", "a": 5, "b": 3}),
                    (format_result, {"value": 42}),
                ]
            )

            # Execute later
            results = await calc_batch()

            assert len(results) == 2
            assert results[0].response == 8
            assert results[0].tool_name == "calculate"
            assert results[1].response == "Result: 42"
            assert results[1].tool_name == "format_result"

    @pytest.mark.asyncio
    async def test_invoke_many_func_deferred_execution(self):
        """Test that invoke_many_func doesn't execute immediately"""

        execution_count = 0

        @tool
        async def counting_tool(x: int) -> int:
            nonlocal execution_count
            execution_count += 1
            return x * 2

        async with Agent("Test agent", tools=[counting_tool]) as agent:
            # Create bound function
            bound_func = agent.invoke_many_func([(counting_tool, {"x": 10})])

            # Tool should not have executed yet
            assert execution_count == 0

            # Execute now
            results = await bound_func()
            assert execution_count == 1
            assert len(results) == 1
            assert results[0].response == 20

            # Can execute again
            await bound_func()
            assert execution_count == 2

    @pytest.mark.asyncio
    async def test_invoke_many_func_with_mixed_types(self):
        """Test invoke_many_func with function references and string names"""

        @tool
        async def tool_x(val: int) -> int:
            return val + 10

        @tool
        async def tool_y(val: int) -> int:
            return val * 10

        async with Agent("Test agent", tools=[tool_x, tool_y]) as agent:
            bound_func = agent.invoke_many_func(
                [(tool_x, {"val": 5}), ("tool_y", {"val": 7})]
            )

            results = await bound_func()
            assert len(results) == 2
            assert results[0].response == 15
            assert results[0].tool_name == "tool_x"
            assert results[1].response == 70
            assert results[1].tool_name == "tool_y"


class TestAgentInvokeEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.mark.asyncio
    async def test_invoke_without_tool_decorator(self):
        """Test invoke with plain function (not decorated with @tool)"""

        async def plain_function(x: int) -> int:
            return x * 2

        async with Agent("Test agent") as agent:
            # Should still work
            result = await agent.invoke(plain_function, x=10)
            assert result.success is True
            assert result.response == 20
            assert result.tool_name == "plain_function"

    @pytest.mark.asyncio
    async def test_invoke_with_complex_return_types(self):
        """Test invoke with tools returning complex types"""

        @tool
        async def return_dict(key: str, value: Any) -> dict:
            return {key: value}

        @tool
        async def return_list(items: int) -> list:
            return list(range(items))

        async with Agent("Test agent", tools=[return_dict, return_list]) as agent:
            # Dict return
            result = await agent.invoke(return_dict, key="test", value=42)
            assert result.response == {"test": 42}

            # List return
            result = await agent.invoke(return_list, items=5)
            assert result.response == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_get_pending_tool_calls(self):
        """Test get_pending_tool_calls method"""

        @tool
        async def dummy_tool(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[dummy_tool]) as agent:
            # No pending calls initially
            assert agent.get_pending_tool_calls() == []

            # Add assistant message with tool calls
            tool_call = ToolCall(
                id="test_call_1",
                type="function",
                function=ToolCallFunction(
                    name="dummy_tool", arguments=json.dumps({"x": 5})
                ),
            )
            agent.assistant.append("", tool_calls=[tool_call])

            # Should have pending call
            pending = agent.get_pending_tool_calls()
            assert len(pending) == 1
            assert pending[0].id == "test_call_1"

            # Resolve the call - now returns an async iterator
            resolved = []
            async for tool_msg in agent.resolve_pending_tool_calls():
                resolved.append(tool_msg)

            # Should have resolved one message
            assert len(resolved) == 1
            assert resolved[0].role == "tool"

            # No more pending calls
            assert agent.get_pending_tool_calls() == []

    @pytest.mark.asyncio
    async def test_resolve_pending_tool_calls_with_invalid_json(self):
        """Test resolve_pending_tool_calls with invalid JSON arguments"""

        @tool
        async def test_tool(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[test_tool]) as agent:
            # Add assistant message with invalid tool call
            tool_call = ToolCall(
                id="bad_call",
                type="function",
                function=ToolCallFunction(name="test_tool", arguments="invalid json"),
            )
            agent.assistant.append("", tool_calls=[tool_call])

            # Resolve should handle the error gracefully - consume the iterator
            resolved = []
            async for tool_msg in agent.resolve_pending_tool_calls():
                resolved.append(tool_msg)

            # Should have resolved one message
            assert len(resolved) == 1

            # Should have error message from Pydantic validation
            # When invalid JSON becomes {}, required fields will be missing
            assert agent[-1].role == "tool"
            assert (
                "validation error" in agent[-1].content.lower()
                or "field required" in agent[-1].content.lower()
            )

    @pytest.mark.asyncio
    async def test_resolve_pending_tool_calls_with_unknown_tool(self):
        """Test resolve_pending_tool_calls with unknown tool name"""

        async with Agent("Test agent") as agent:
            # Add assistant message with unknown tool call
            tool_call = ToolCall(
                id="unknown_call",
                type="function",
                function=ToolCallFunction(
                    name="unknown_tool", arguments=json.dumps({"x": 5})
                ),
            )
            agent.assistant.append("", tool_calls=[tool_call])

            # Resolve should handle gracefully - consume the iterator
            resolved = []
            async for tool_msg in agent.resolve_pending_tool_calls():
                resolved.append(tool_msg)

            # Should have resolved one message
            assert len(resolved) == 1

            # Should have error message
            assert agent[-1].role == "tool"
            assert "not found" in agent[-1].content

    @pytest.mark.asyncio
    async def test_invoke_events(self):
        """Test that invoke emits proper events"""

        events = []

        @tool
        async def event_tool(x: int) -> int:
            return x * 2

        async with Agent("Test agent", tools=[event_tool]) as agent:

            def event_handler(ctx):
                # Extract parameters from the context
                events.append(ctx.parameters)

            agent.on("tool:call:before")(event_handler)
            agent.on("tool:call:after")(event_handler)

            await agent.invoke(event_tool, x=10)

            # Wait for all events to be processed
            await agent.join()

            # Should have 2 events
            assert len(events) == 2

            # Check tool:call event data
            call_event = events[0]
            assert call_event["tool_name"] == "event_tool"
            assert call_event["parameters"] == {"x": 10}
            assert "tool_call_id" in call_event

            # Check tool:response event data
            response_event = events[1]
            assert response_event["tool_name"] == "event_tool"
            assert response_event["success"] is True
            assert response_event["response"].response == 20
            assert "tool_call_id" in response_event

    @pytest.mark.asyncio
    async def test_invoke_with_none_return(self):
        """Test invoke with tool that returns None"""

        @tool
        async def void_tool(message: str) -> None:
            # Tool that performs side effect but returns nothing
            pass

        async with Agent("Test agent", tools=[void_tool]) as agent:
            result = await agent.invoke(void_tool, message="test")
            assert result.success is True
            assert result.response is None
            assert agent[-1].content == "None"
