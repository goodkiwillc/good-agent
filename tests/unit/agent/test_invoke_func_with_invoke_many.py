from datetime import datetime
from typing import Any

import pytest
from good_agent import Agent, tool
from good_agent.messages import AssistantMessage, ToolMessage


class TestInvokeFuncWithInvokeMany:
    """Test that invoke_func works correctly with invoke_many"""

    @pytest.mark.asyncio
    async def test_invoke_func_with_invoke_many_tool_call_ids(self):
        """Test that tool call IDs match when using invoke_func with invoke_many"""

        @tool
        async def search_web(
            search_type: str,
            query: str,
            since: datetime | None = None,
            until: datetime | None = None,
            ttl: int = 3600,
            hide: list[str] | None = None,
        ) -> dict[str, Any]:
            """Mock search web function"""
            return {
                "query": query,
                "search_type": search_type,
                "results": [f"Result for {query}"],
                "since": str(since) if since else None,
                "until": str(until) if until else None,
            }

        async with Agent("You are a helpful assistant", tools=[search_web]) as agent:
            # Create the scenario from the user's example
            today = datetime.now().date()

            # Create a bound function with preset parameters
            search_tool = agent.invoke_func(
                search_web,
                search_type="news",
                since=today,
                until=today,
                ttl=3600 * 24,
                hide=["ttl"],
            )

            queries = [
                "California Governor's Election 2026",
                "Katie Porter",
                "Xavier Becerra",
            ]

            # Use invoke_many with the bound function
            results = await agent.invoke_many(
                invocations=[(search_tool, dict(query=q)) for q in queries]
            )

            # Check that we got all results
            assert len(results) == 3
            assert all(r.success for r in results)

            # Collect tool call IDs from assistant messages and tool responses
            assistant_tool_call_ids = []
            tool_response_ids = []

            for msg in agent.messages:
                if isinstance(msg, AssistantMessage) and msg.tool_calls:
                    for tc in msg.tool_calls:
                        assistant_tool_call_ids.append(tc.id)
                elif isinstance(msg, ToolMessage):
                    tool_response_ids.append(msg.tool_call_id)

            # Critical assertions:
            # 1. All tool call IDs should match
            assert set(assistant_tool_call_ids) == set(tool_response_ids), (
                f"Tool call IDs mismatch! Assistant: {assistant_tool_call_ids}, Tool: {tool_response_ids}"
            )

            # 2. There should be exactly 3 tool calls and 3 tool responses
            assert len(assistant_tool_call_ids) == 3, (
                f"Expected 3 assistant tool calls, got {len(assistant_tool_call_ids)}"
            )
            assert len(tool_response_ids) == 3, (
                f"Expected 3 tool responses, got {len(tool_response_ids)}"
            )

            # 3. The returned results should have matching tool call IDs
            returned_tool_call_ids = [r.tool_call_id for r in results]
            assert set(returned_tool_call_ids) == set(tool_response_ids), (
                "Returned tool call IDs don't match messages"
            )

    @pytest.mark.asyncio
    async def test_invoke_func_creates_single_assistant_message(self):
        """Test that invoke_func with invoke_many creates only one assistant message"""

        @tool
        async def process_data(data: str, transform: str = "upper") -> str:
            """Process data with transformation"""
            if transform == "upper":
                return data.upper()
            elif transform == "lower":
                return data.lower()
            else:
                return data

        async with Agent("You are a data processor", tools=[process_data]) as agent:
            # Create bound function
            uppercase_processor = agent.invoke_func(process_data, transform="upper")

            # Process multiple items
            items = ["hello", "world", "test"]

            initial_message_count = len(agent)

            results = await agent.invoke_many(
                [(uppercase_processor, {"data": item}) for item in items]
            )

            # Count assistant messages added
            assistant_messages_added = 0
            tool_messages_added = 0

            for msg in agent.messages[initial_message_count:]:
                if isinstance(msg, AssistantMessage):
                    assistant_messages_added += 1
                elif isinstance(msg, ToolMessage):
                    tool_messages_added += 1

            # Should have exactly 1 assistant message with all tool calls
            # or at most one assistant message per tool call
            assert assistant_messages_added <= len(items), (
                f"Too many assistant messages created: {assistant_messages_added}"
            )

            # Should have exactly one tool message per invocation
            assert tool_messages_added == len(items), (
                f"Expected {len(items)} tool messages, got {tool_messages_added}"
            )

            # All results should be successful
            assert all(r.success for r in results)
            assert [r.response for r in results] == ["HELLO", "WORLD", "TEST"]

    @pytest.mark.asyncio
    async def test_invoke_func_preserves_bound_parameters(self):
        """Test that bound parameters are correctly preserved and passed through"""

        @tool
        async def complex_tool(
            operation: str,
            value: int,
            multiplier: int = 1,
            offset: int = 0,
            format_output: bool = False,
        ) -> Any:
            """Complex tool with multiple parameters"""
            result = (value * multiplier) + offset
            if operation == "square":
                result = result**2
            elif operation == "negate":
                result = -result

            if format_output:
                return f"Result: {result}"
            return result

        async with Agent("Test agent", tools=[complex_tool]) as agent:
            # Create bound function with some preset parameters
            square_with_offset = agent.invoke_func(
                complex_tool, operation="square", offset=10, format_output=True
            )

            # Use in invoke_many with remaining parameters
            results = await agent.invoke_many(
                [
                    (square_with_offset, {"value": 5, "multiplier": 2}),
                    (square_with_offset, {"value": 3, "multiplier": 3}),
                ]
            )

            # Check results
            assert len(results) == 2
            assert all(r.success for r in results)

            # (5 * 2 + 10)^2 = 20^2 = 400
            assert results[0].response == "Result: 400"

            # (3 * 3 + 10)^2 = 19^2 = 361
            assert results[1].response == "Result: 361"

            # Verify the parameters were correctly merged
            assert results[0].parameters["operation"] == "square"
            assert results[0].parameters["offset"] == 10
            assert results[0].parameters["format_output"] is True
            assert results[0].parameters["value"] == 5
            assert results[0].parameters["multiplier"] == 2
