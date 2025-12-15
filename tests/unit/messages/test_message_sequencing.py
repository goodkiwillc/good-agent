import pytest

from good_agent import Agent, tool
from good_agent.messages import (
    AssistantMessage,
    ToolMessage,
)


class TestMessageSequencing:
    """Test that message sequencing follows LLM requirements"""

    @pytest.mark.asyncio
    async def test_tool_responses_immediately_follow_assistant(self):
        """Test that tool responses immediately follow their assistant message"""

        @tool
        async def get_weather(location: str) -> str:
            return f"Weather in {location}: Sunny, 72°F"

        @tool
        async def get_time(timezone: str) -> str:
            return f"Time in {timezone}: 3:45 PM"

        async with Agent("You are helpful", tools=[get_weather, get_time]) as agent:
            # Add user message
            agent.append("What's the weather and time?")

            # Use invoke_many for parallel execution
            await agent.invoke_many(
                [
                    (get_weather, {"location": "Paris"}),
                    (get_time, {"timezone": "Europe/Paris"}),
                ]
            )

            # Validate sequencing
            messages = list(agent.messages)

            # Find all assistant messages with tool calls
            for i, msg in enumerate(messages):
                if isinstance(msg, AssistantMessage) and msg.tool_calls:
                    tool_call_ids = [tc.id for tc in msg.tool_calls]

                    # The next N messages should be tool responses for these calls
                    expected_responses = len(tool_call_ids)

                    tool_messages: list[ToolMessage] = []
                    for j in range(1, expected_responses + 1):
                        next_msg = messages[i + j] if i + j < len(messages) else None

                        assert next_msg is not None, f"Missing tool response at position {i + j}"
                        assert isinstance(next_msg, ToolMessage), (
                            f"Expected ToolMessage at position {i + j}, got {type(next_msg).__name__}"
                        )
                        assert next_msg.tool_call_id in tool_call_ids, (
                            f"Tool response {next_msg.tool_call_id} not in expected IDs {tool_call_ids}"
                        )
                        tool_messages.append(next_msg)

                    # Remove found IDs to check all are accounted for
                    found_ids = {tool_msg.tool_call_id for tool_msg in tool_messages}

                    assert found_ids == set(tool_call_ids), (
                        f"Not all tool calls have responses. Expected: {tool_call_ids}, Found: {found_ids}"
                    )

    @pytest.mark.asyncio
    async def test_parallel_tools_single_assistant_message(self):
        """Test that parallel tool calls are in a single assistant message"""

        @tool
        async def tool_a(x: int) -> int:
            return x + 1

        @tool
        async def tool_b(x: int) -> int:
            return x * 2

        @tool
        async def tool_c(x: int) -> int:
            return x**2

        async with Agent("Test agent", tools=[tool_a, tool_b, tool_c]) as agent:
            agent.append("Process these numbers")

            # Execute multiple tools in parallel
            await agent.invoke_many([(tool_a, {"x": 5}), (tool_b, {"x": 5}), (tool_c, {"x": 5})])

            # Count assistant messages with tool calls
            assistant_with_tools = [
                msg
                for msg in agent.messages
                if isinstance(msg, AssistantMessage) and msg.tool_calls
            ]

            # Should be exactly 1 assistant message with all 3 tool calls
            assert len(assistant_with_tools) == 1, (
                f"Expected 1 assistant message with tool calls, got {len(assistant_with_tools)}"
            )

            # That message should have all 3 tool calls
            tool_calls = assistant_with_tools[0].tool_calls
            assert tool_calls is not None
            assert len(tool_calls) == 3, (
                f"Expected 3 tool calls in assistant message, got {len(tool_calls)}"
            )

    @pytest.mark.asyncio
    async def test_mixed_invoke_func_breaks_sequencing(self):
        """Test that mixing invoke_func with regular tools breaks sequencing"""

        @tool
        async def search_web(query: str, source: str = "web") -> str:
            return f"Results for '{query}' from {source}"

        async with Agent("Test agent", tools=[search_web]) as agent:
            # Create bound function
            news_search = agent.invoke_func(search_web, source="news")
            web_search = agent.invoke_func(search_web, source="web")

            agent.append("Search for Python tutorials")

            # This WILL create bad sequencing with current implementation
            await agent.invoke_many(
                [
                    (news_search, {"query": "Python tutorials"}),
                    (web_search, {"query": "Python tutorials"}),
                    (search_web, {"query": "Python basics"}),  # Regular tool
                ]
            )

            # Check message sequence
            messages = list(agent.messages)

            # With current broken implementation, we'll see:
            # System, User, Assistant(news), Tool(news), Assistant(web), Tool(web), Assistant(regular), Tool(regular)
            # This is WRONG - tool responses aren't immediately after their assistant message

            # Count assistant messages with tool calls
            assistant_msgs = [
                (i, msg)
                for i, msg in enumerate(messages)
                if isinstance(msg, AssistantMessage) and msg.tool_calls
            ]

            # Document the broken behavior (this will fail with proper implementation)
            if len(assistant_msgs) > 1:
                # Current broken behavior - multiple assistant messages
                for _i, (idx, assistant_msg) in enumerate(assistant_msgs):
                    # Check if tool response immediately follows
                    next_msg = messages[idx + 1] if idx + 1 < len(messages) else None

                    # In broken implementation, the sequencing might be wrong
                    # This test documents that issue
                    if next_msg and isinstance(next_msg, ToolMessage):
                        # Check if it's the right tool response
                        tool_calls = assistant_msg.tool_calls
                        assert tool_calls is not None
                        tool_call_id = tool_calls[0].id
                        if next_msg.tool_call_id != tool_call_id:
                            # This indicates broken sequencing!
                            pytest.fail(
                                f"Broken sequencing: Tool response {next_msg.tool_call_id} "
                                f"doesn't match assistant tool call {tool_call_id}"
                            )

    @pytest.mark.asyncio
    async def test_invoke_many_with_only_bound_functions(self):
        """Test invoke_many when all invocations are bound functions"""

        @tool
        async def process_data(data: str, operation: str) -> str:
            return f"{operation}({data})"

        async with Agent("Test agent", tools=[process_data]) as agent:
            # Create multiple bound functions
            upper_processor = agent.invoke_func(process_data, operation="UPPER")
            lower_processor = agent.invoke_func(process_data, operation="lower")
            title_processor = agent.invoke_func(process_data, operation="Title")

            agent.append("Process this data")

            # All bound functions - should each create their own assistant/tool pairs
            await agent.invoke_many(
                [
                    (upper_processor, {"data": "hello"}),
                    (lower_processor, {"data": "WORLD"}),
                    (title_processor, {"data": "test case"}),
                ]
            )

            # With current implementation, each creates its own assistant message
            # This is actually OK since each maintains proper sequencing
            messages = list(agent.messages)

            # Verify each assistant message is followed by its tool response
            for i, msg in enumerate(messages):
                if isinstance(msg, AssistantMessage) and msg.tool_calls:
                    next_msg = messages[i + 1] if i + 1 < len(messages) else None
                    assert isinstance(next_msg, ToolMessage), (
                        f"Assistant at {i} not followed by tool response"
                    )

                    # Tool response should match the tool call
                    tool_calls = msg.tool_calls
                    assert tool_calls is not None
                    assert next_msg.tool_call_id == tool_calls[0].id, (
                        f"Tool response ID mismatch at position {i + 1}"
                    )

    @pytest.mark.asyncio
    async def test_model_parallel_tool_support(self):
        """Test that we properly consolidate when model supports parallel tools"""

        @tool
        async def fetch_data(source: str) -> str:
            return f"Data from {source}"

        # Most modern models support parallel tool calls
        # GPT-4, Claude 3+, etc. all support this
        async with Agent("Test agent", model="gpt-4", tools=[fetch_data]) as agent:
            agent.append("Fetch data from multiple sources")

            # These should be consolidated into one assistant message
            await agent.invoke_many(
                [
                    (fetch_data, {"source": "database"}),
                    (fetch_data, {"source": "api"}),
                    (fetch_data, {"source": "cache"}),
                ]
            )

            # Find assistant messages with tool calls
            assistant_msgs = [
                msg
                for msg in agent.messages
                if isinstance(msg, AssistantMessage) and msg.tool_calls
            ]

            # Should be consolidated into one message
            assert len(assistant_msgs) == 1, (
                f"Expected 1 consolidated assistant message, got {len(assistant_msgs)}"
            )

            # With all three tool calls
            tool_calls = assistant_msgs[0].tool_calls
            assert tool_calls is not None
            assert len(tool_calls) == 3, f"Expected 3 tool calls in message, got {len(tool_calls)}"

            # Followed by three tool responses
            idx = agent.messages.index(assistant_msgs[0])
            for i in range(1, 4):
                tool_msg = agent.messages[idx + i]
                assert isinstance(tool_msg, ToolMessage), (
                    f"Expected ToolMessage at position {idx + i}, got {type(tool_msg).__name__}"
                )
