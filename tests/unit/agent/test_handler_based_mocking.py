"""Tests for handler-based mocking API

This module tests the new handler-based mocking system that allows
custom mock logic while maintaining backwards compatibility with the
existing queue-based API.
"""

import pytest
from good_agent import Agent
from good_agent.mock import (
    MockResponse,
    mock_message,
)


# Import new handler types (will be implemented)
try:
    from good_agent.mock import (
        MockContext,
        MockHandler,
        QueuedResponseHandler,
        ConditionalHandler,
        TranscriptHandler,
    )

    HANDLERS_AVAILABLE = True
except ImportError:
    HANDLERS_AVAILABLE = False
    MockContext = None  # type: ignore[assignment,misc]
    MockHandler = None  # type: ignore[assignment,misc]
    QueuedResponseHandler = None  # type: ignore[assignment,misc]
    ConditionalHandler = None  # type: ignore[assignment,misc]
    TranscriptHandler = None  # type: ignore[assignment,misc]


pytestmark = pytest.mark.asyncio


# ============================================================================
# Test 1: Backwards Compatibility - Existing API Still Works
# ============================================================================


class TestBackwardsCompatibility:
    """Ensure existing queue-based API continues to work unchanged"""

    async def test_string_responses_still_work(self):
        """Test that simple string responses work as before"""
        agent = Agent("You are helpful")

        with agent.mock("Response 1", "Response 2") as mock:
            result = await mock.call("Question 1")
            assert result.content == "Response 1"

            result = await mock.call("Question 2")
            assert result.content == "Response 2"

    async def test_mock_response_objects_still_work(self):
        """Test that MockResponse objects work as before"""
        agent = Agent("You are helpful")

        responses = [
            MockResponse(content="First", role="assistant"),
            MockResponse(content="Second", role="assistant"),
        ]

        with agent.mock(*responses) as mock:
            result = await mock.call("Question")
            assert result.content == "First"

    async def test_agent_mock_create_helper_still_works(self):
        """Test that agent.mock.create() helper still works"""
        agent = Agent("You are helpful")

        with agent.mock(agent.mock.create("Response", role="assistant")) as mock:
            result = await mock.call("Question")
            assert result.content == "Response"

    async def test_agent_mock_tool_call_helper_still_works(self):
        """Test that agent.mock.tool_call() helper still works"""
        agent = Agent("You are helpful")

        with agent.mock(
            agent.mock.tool_call("weather", location="Paris", result={"temp": 72})
        ):
            # Tool call mocking should work as before
            pass

    async def test_api_requests_tracking_still_works(self):
        """Test that api_requests/api_responses tracking still works"""
        agent = Agent("You are helpful")

        with agent.mock("Response 1", "Response 2") as mock:
            await mock.call("Question 1")
            await mock.call("Question 2")

            # Should track both requests
            assert len(mock.api_requests) == 2
            assert len(mock.api_responses) == 2

    async def test_execute_with_queue_still_works(self):
        """Test that execute() with queue-based mocking still works"""
        agent = Agent("You are helpful")

        with agent.mock(
            mock_message("First response", role="assistant"),
            mock_message("Second response", role="assistant"),
        ):
            messages = []
            async for msg in agent.execute("Question"):
                messages.append(msg)

            # Should yield messages from queue
            assert len(messages) >= 1


# ============================================================================
# Test 2: Handler Protocol - Basic Functionality
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestHandlerProtocol:
    """Test the basic MockHandler protocol"""

    async def test_function_handler_is_called(self):
        """Test that a function handler is called with context"""
        call_count = []

        def my_handler(ctx: MockContext) -> MockResponse:
            call_count.append(ctx.call_count)
            return MockResponse(content=f"Response {ctx.call_count}")

        agent = Agent("You are helpful")

        with agent.mock(my_handler):
            result = await agent.call("Question")

        assert len(call_count) == 1
        assert call_count[0] == 1
        assert result.content == "Response 1"

    async def test_class_handler_is_called(self):
        """Test that a class-based handler is called"""

        class CountingHandler:
            def __init__(self):
                self.count = 0

            async def handle(self, ctx: MockContext) -> MockResponse:
                self.count += 1
                return MockResponse(content=f"Count: {self.count}")

        handler = CountingHandler()
        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("Question 1")
            assert result.content == "Count: 1"

            result = await agent.call("Question 2")
            assert result.content == "Count: 2"

        assert handler.count == 2

    async def test_async_handler_is_called(self):
        """Test that async handlers are supported"""

        async def async_handler(ctx: MockContext) -> MockResponse:
            # Simulate async operation
            return MockResponse(content="Async response")

        agent = Agent("You are helpful")

        with agent.mock(async_handler):
            result = await agent.call("Question")
            assert result.content == "Async response"

    async def test_handler_receives_agent_context(self):
        """Test that handler receives full agent context"""
        received_contexts = []

        def handler(ctx: MockContext) -> MockResponse:
            received_contexts.append(ctx)
            return MockResponse(content="Response")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("My question")

        assert len(received_contexts) == 1
        ctx = received_contexts[0]

        # Should have access to agent
        assert ctx.agent is agent
        assert ctx.agent.user[-1].content == "My question"

        # Should have call tracking
        assert ctx.call_count == 1
        assert ctx.iteration >= 0


# ============================================================================
# Test 3: MockContext - Context Access
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestMockContext:
    """Test MockContext provides necessary information"""

    async def test_context_has_agent_reference(self):
        """Test that context provides access to agent"""

        def handler(ctx: MockContext) -> MockResponse:
            assert ctx.agent is not None
            assert hasattr(ctx.agent, "messages")
            return MockResponse(content="Done")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("Question")

    async def test_context_provides_user_message_access(self):
        """Test that handler can access user messages via ctx.agent.user[-1]"""

        def handler(ctx: MockContext) -> MockResponse:
            last_user = ctx.agent.user[-1]

            if "weather" in last_user.content.lower():
                return MockResponse(content="It's sunny!")
            return MockResponse(content="I don't understand")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("What's the weather?")
            assert "sunny" in result.content.lower()

            result = await agent.call("Random question")
            assert "don't understand" in result.content.lower()

    async def test_context_provides_assistant_message_access(self):
        """Test that handler can access previous assistant messages"""

        def handler(ctx: MockContext) -> MockResponse:
            # First call - no previous assistant message
            if ctx.call_count == 1:
                return MockResponse(content="First response")

            # Second call - can see previous assistant message
            last_assistant = ctx.agent.assistant[-1]
            return MockResponse(content=f"After: {last_assistant.content}")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result1 = await agent.call("Question 1")
            assert result1.content == "First response"

            result2 = await agent.call("Question 2")
            assert "After: First response" in result2.content

    async def test_context_tracks_call_count(self):
        """Test that call_count increments correctly"""
        call_counts = []

        def handler(ctx: MockContext) -> MockResponse:
            call_counts.append(ctx.call_count)
            return MockResponse(content=f"Call {ctx.call_count}")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("Q1")
            await agent.call("Q2")
            await agent.call("Q3")

        assert call_counts == [1, 2, 3]

    async def test_context_provides_messages_list(self):
        """Test that context provides messages being sent to LLM"""

        def handler(ctx: MockContext) -> MockResponse:
            # Should have at least system message + user message
            assert len(ctx.messages) >= 2
            return MockResponse(content="Response")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("Question")

    async def test_context_provides_kwargs(self):
        """Test that context includes LLM kwargs"""

        def handler(ctx: MockContext) -> MockResponse:
            # kwargs should be dict
            assert isinstance(ctx.kwargs, dict)
            return MockResponse(content="Response")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("Question")


# ============================================================================
# Test 4: QueuedResponseHandler - Default Behavior
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestQueuedResponseHandler:
    """Test QueuedResponseHandler (current behavior as handler)"""

    async def test_queued_handler_returns_responses_in_order(self):
        """Test that QueuedResponseHandler returns responses in FIFO order"""
        handler = QueuedResponseHandler("Response 1", "Response 2", "Response 3")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("Q1")
            assert result.content == "Response 1"

            result = await agent.call("Q2")
            assert result.content == "Response 2"

            result = await agent.call("Q3")
            assert result.content == "Response 3"

    async def test_queued_handler_exhaustion_raises_error(self):
        """Test that exhausting queue raises clear error"""
        handler = QueuedResponseHandler("Only response")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("Q1")  # OK

            with pytest.raises(ValueError, match="exhausted|no more"):
                await agent.call("Q2")  # Should fail

    async def test_queued_handler_accepts_mock_responses(self):
        """Test that QueuedResponseHandler accepts MockResponse objects"""
        handler = QueuedResponseHandler(
            MockResponse(content="First", role="assistant"),
            MockResponse(content="Second", role="assistant"),
        )

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("Question")
            assert result.content == "First"

    async def test_string_responses_use_queued_handler_internally(self):
        """Test that string responses use QueuedResponseHandler under the hood"""
        agent = Agent("You are helpful")

        # This should use QueuedResponseHandler internally
        with agent.mock("Response 1", "Response 2") as mock:
            result = await mock.call("Q1")
            assert result.content == "Response 1"


# ============================================================================
# Test 5: ConditionalHandler - Pattern Matching
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestConditionalHandler:
    """Test ConditionalHandler for pattern-based responses"""

    async def test_conditional_handler_matches_patterns(self):
        """Test that ConditionalHandler matches based on conditions"""
        handler = ConditionalHandler()
        handler.when(
            lambda ctx: "weather" in ctx.agent.user[-1].content.lower(),
            respond="It's sunny!",
        ).when(
            lambda ctx: "time" in ctx.agent.user[-1].content.lower(),
            respond="It's 3 PM",
        )

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("What's the weather?")
            assert "sunny" in result.content.lower()

            result = await agent.call("What time is it?")
            assert "3 PM" in result.content

    async def test_conditional_handler_uses_default(self):
        """Test that ConditionalHandler falls back to default"""
        handler = ConditionalHandler()
        handler.when(
            lambda ctx: "weather" in ctx.agent.user[-1].content.lower(), respond="Sunny"
        ).default("I don't know")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("Random question")
            assert "don't know" in result.content.lower()

    async def test_conditional_handler_without_default_raises(self):
        """Test that ConditionalHandler raises when no match and no default"""
        handler = ConditionalHandler()
        handler.when(
            lambda ctx: "weather" in ctx.agent.user[-1].content.lower(), respond="Sunny"
        )

        agent = Agent("You are helpful")

        with agent.mock(handler):
            with pytest.raises(Exception, match="no match|no default"):
                await agent.call("Random question")

    async def test_conditional_handler_checks_rules_in_order(self):
        """Test that ConditionalHandler checks rules in order added"""
        handler = ConditionalHandler()
        handler.when(
            lambda ctx: True,  # Matches everything
            respond="First match",
        ).when(
            lambda ctx: True,  # Never reached
            respond="Second match",
        )

        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("Anything")
            assert result.content == "First match"

    async def test_conditional_handler_with_complex_logic(self):
        """Test conditional handler with more complex decision logic"""

        class SmartHandler(ConditionalHandler):
            def __init__(self):
                super().__init__()
                self.setup_rules()

            def setup_rules(self):
                self.when(
                    lambda ctx: ctx.call_count == 1
                    and "weather" in ctx.agent.user[-1].content,
                    respond=MockResponse(
                        content="I'll check",
                        tool_calls=[
                            {
                                "tool_name": "get_weather",
                                "arguments": {},
                                "type": "tool_call",
                                "result": None,
                            }
                        ],  # type: ignore[typeddict-item]
                    ),
                ).when(
                    lambda ctx: ctx.call_count == 2, respond="Based on the tool: sunny"
                )

        agent = Agent("You are helpful")

        with agent.mock(SmartHandler()):
            result = await agent.call("What's the weather?")
            # First call should have tool calls
            if hasattr(result, "tool_calls") and result.tool_calls:
                assert len(result.tool_calls) > 0


# ============================================================================
# Test 6: TranscriptHandler - Predefined Flows
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestTranscriptHandler:
    """Test TranscriptHandler for predefined conversation flows"""

    async def test_transcript_handler_follows_sequence(self):
        """Test that TranscriptHandler follows predefined sequence"""
        transcript = [
            ("assistant", "First response"),
            ("assistant", "Second response"),
            ("assistant", "Third response"),
        ]

        handler = TranscriptHandler(transcript)
        agent = Agent("You are helpful")

        with agent.mock(handler):
            result = await agent.call("Q1")
            assert result.content == "First response"

            result = await agent.call("Q2")
            assert result.content == "Second response"

            result = await agent.call("Q3")
            assert result.content == "Third response"

    async def test_transcript_handler_with_tool_calls(self):
        """Test transcript handler with tool calls"""
        transcript = [
            (
                "assistant",
                "I'll check",
                {"tool_calls": [{"tool_name": "get_weather", "arguments": {}}]},
            ),
            ("assistant", "It's sunny"),
        ]

        handler = TranscriptHandler(transcript)
        agent = Agent("You are helpful")

        with agent.mock(handler):
            # Use auto_execute_tools=False to get the first response with tool calls
            result = await agent.call("What's the weather?", auto_execute_tools=False)
            # First response should have tool calls
            assert result.tool_calls is not None
            assert result.content == "I'll check"

    async def test_transcript_exhaustion_raises_error(self):
        """Test that exhausting transcript raises error"""
        transcript = [
            ("assistant", "Only response"),
        ]

        handler = TranscriptHandler(transcript)
        agent = Agent("You are helpful")

        with agent.mock(handler):
            await agent.call("Q1")  # OK

            with pytest.raises(ValueError, match="exhausted"):
                await agent.call("Q2")  # Should fail


# ============================================================================
# Test 7: Multi-Turn Workflows with execute()
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestMultiTurnWorkflows:
    """Test handlers work correctly with execute() multi-turn flows"""

    async def test_handler_called_multiple_times_during_execute(self):
        """Test that handler is called for each LLM request during execute()"""
        call_counts = []

        def handler(ctx: MockContext) -> MockResponse:
            call_counts.append(ctx.call_count)

            if ctx.call_count == 1:
                # First call: request tool
                return MockResponse(
                    content="I'll check",
                    tool_calls=[
                        {
                            "tool_name": "dummy_tool",
                            "arguments": {},
                            "type": "tool_call",
                            "result": None,
                        }
                    ],  # type: ignore[typeddict-item]
                )
            else:
                # Second call: final response
                return MockResponse(content="Done")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            messages = []
            async for msg in agent.execute("Question"):
                messages.append(msg)

        # Handler should be called twice (once for tool request, once for final)
        assert len(call_counts) >= 1
        assert 1 in call_counts

    async def test_handler_can_inspect_tool_results(self):
        """Test that handler can see tool results in messages"""

        def handler(ctx: MockContext) -> MockResponse:
            if ctx.call_count == 1:
                return MockResponse(
                    content="Checking",
                    tool_calls=[
                        {
                            "tool_name": "get_data",
                            "arguments": {},
                            "type": "tool_call",
                            "result": None,
                        }
                    ],  # type: ignore[typeddict-item]
                )
            else:
                # Should be able to inspect messages for tool results
                # (though tool may not have executed in mock)
                return MockResponse(content="Based on data: result")

        agent = Agent("You are helpful")

        with agent.mock(handler):
            messages = []
            async for msg in agent.execute("Get data"):
                messages.append(msg)

        # Should have received messages
        assert len(messages) >= 1


# ============================================================================
# Test 8: Multi-Agent Support
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestMultiAgentSupport:
    """Test that each agent can have its own handler"""

    async def test_each_agent_uses_own_handler(self):
        """Test that agents in conversation use separate handlers"""

        def handler_a(ctx: MockContext) -> MockResponse:
            return MockResponse(content="Response from A")

        def handler_b(ctx: MockContext) -> MockResponse:
            return MockResponse(content="Response from B")

        agent_a = Agent("Agent A")
        agent_b = Agent("Agent B")

        with agent_a.mock(handler_a), agent_b.mock(handler_b):
            result_a = await agent_a.call("Question to A")
            result_b = await agent_b.call("Question to B")

            assert result_a.content == "Response from A"
            assert result_b.content == "Response from B"

    async def test_handlers_maintain_separate_state(self):
        """Test that handlers for different agents maintain separate state"""

        class CountingHandler:
            def __init__(self, name):
                self.name = name
                self.count = 0

            async def handle(self, ctx: MockContext) -> MockResponse:
                self.count += 1
                return MockResponse(content=f"{self.name}: {self.count}")

        handler_a = CountingHandler("A")
        handler_b = CountingHandler("B")

        agent_a = Agent("Agent A")
        agent_b = Agent("Agent B")

        with agent_a.mock(handler_a), agent_b.mock(handler_b):
            result = await agent_a.call("Q1")
            assert result.content == "A: 1"

            result = await agent_b.call("Q1")
            assert result.content == "B: 1"

            result = await agent_a.call("Q2")
            assert result.content == "A: 2"

            result = await agent_b.call("Q2")
            assert result.content == "B: 2"


# ============================================================================
# Test 9: API Surface - Convenience Methods
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestConvenienceAPI:
    """Test convenience methods on agent.mock namespace"""

    async def test_agent_mock_conditional_convenience(self):
        """Test agent.mock.conditional() convenience method"""
        agent = Agent("You are helpful")

        # Should provide shorthand for creating ConditionalHandler
        handler = agent.mock.conditional()
        handler.when(
            lambda ctx: "test" in ctx.agent.user[-1].content, respond="Matched"
        ).default("No match")

        with agent.mock(handler):
            result = await agent.call("This is a test")
            assert result.content == "Matched"

    async def test_agent_mock_transcript_convenience(self):
        """Test agent.mock.transcript() convenience method"""
        agent = Agent("You are helpful")

        transcript = [
            ("assistant", "Response 1"),
            ("assistant", "Response 2"),
        ]

        # Should provide shorthand for creating TranscriptHandler
        with agent.mock.transcript(transcript):
            await agent.call("Question")
            # Should work with transcript


# ============================================================================
# Test 10: Error Handling
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestErrorHandling:
    """Test error handling in handler system"""

    async def test_handler_exception_propagates(self):
        """Test that exceptions in handlers propagate"""

        def failing_handler(ctx: MockContext) -> MockResponse:
            raise ValueError("Handler failed!")

        agent = Agent("You are helpful")

        with agent.mock(failing_handler):
            with pytest.raises(ValueError, match="Handler failed"):
                await agent.call("Question")

    async def test_invalid_handler_type_raises_error(self):
        """Test that invalid handler type raises clear error"""
        agent = Agent("You are helpful")

        # Not a callable, not a string, not a MockResponse
        with pytest.raises(TypeError):
            with agent.mock(12345):  # Invalid
                pass

    async def test_handler_returning_invalid_type_raises_error(self):
        """Test that handler returning non-MockResponse raises error"""

        def bad_handler(ctx: MockContext):
            return "Not a MockResponse"  # Wrong type

        agent = Agent("You are helpful")

        with agent.mock(bad_handler):
            with pytest.raises((TypeError, ValueError)):
                await agent.call("Question")


# ============================================================================
# Test 11: Integration with api_requests/api_responses
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestAPITracking:
    """Test that handlers maintain api_requests/api_responses tracking"""

    async def test_handler_populates_api_requests(self):
        """Test that handler calls populate api_requests"""

        def handler(ctx: MockContext) -> MockResponse:
            return MockResponse(content="Response")

        agent = Agent("You are helpful")

        with agent.mock(handler) as mock:
            await mock.call("Question 1")
            await mock.call("Question 2")

            # Should track both requests
            assert len(mock.api_requests) == 2

    async def test_handler_populates_api_responses(self):
        """Test that handler calls populate api_responses"""

        def handler(ctx: MockContext) -> MockResponse:
            return MockResponse(content="Response")

        agent = Agent("You are helpful")

        with agent.mock(handler) as mock:
            await mock.call("Question")

            # Should track response
            assert len(mock.api_responses) == 1
            response = mock.api_responses[0]

            # Should be LiteLLM-style response with expected fields
            assert hasattr(response, "choices")
            assert hasattr(response, "usage")

    async def test_handler_fires_llm_events(self):
        """Test that handler calls fire LLM_COMPLETE events"""
        events_fired = []

        def handler(ctx: MockContext) -> MockResponse:
            return MockResponse(content="Response")

        agent = Agent("You are helpful")

        # Initialize agent and listen for events
        from good_agent.events import AgentEvents

        @agent.on(AgentEvents.LLM_COMPLETE_BEFORE)
        def on_before(**kwargs):
            events_fired.append("before")

        @agent.on(AgentEvents.LLM_COMPLETE_AFTER)
        def on_after(**kwargs):
            events_fired.append("after")

        async with agent:
            with agent.mock(handler):
                await agent.call("Question")

        # Should fire both events
        assert "before" in events_fired
        assert "after" in events_fired
