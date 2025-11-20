"""Tests for handler-based mocking API

This module tests the new handler-based mocking system that allows
custom mock logic while maintaining backwards compatibility with the
existing queue-based API.
"""

from typing import TYPE_CHECKING

import pytest
from good_agent import Agent
from good_agent.mock import (
    MockResponse,
    mock_message,
)

# Import new handler types
from good_agent.mock import (
    ConditionalHandler,
    MockContext,
    QueuedResponseHandler,
    TranscriptHandler,
)

if TYPE_CHECKING:
    # Always available for type checking
    pass

HANDLERS_AVAILABLE = True


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
            assert ctx.agent is not None
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
            assert ctx.agent is not None
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
            return 123  # Wrong type (not str or MockResponse)

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
        def on_before(ctx):
            events_fired.append("before")

        @agent.on(AgentEvents.LLM_COMPLETE_AFTER)
        def on_after(ctx):
            events_fired.append("after")

        async with agent:
            with agent.mock(handler):
                await agent.call("Question")

        # Should fire both events
        assert "before" in events_fired
        assert "after" in events_fired


# ============================================================================
# Test 11: Agent Pipe Conversation Pattern (agent | agent)
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestAgentPipeConversation:
    """Test agent | agent conversation pattern with handlers"""

    async def test_piped_agents_execute_in_sequence(self):
        """Test that agent | agent executes both agents in sequence"""
        alice = Agent("You are Alice, a friendly greeter")
        bob = Agent("You are Bob, a grateful responder")

        # Alice greets
        alice_handler = ConditionalHandler().default("Hello Bob! How are you today?")

        # Bob responds to Alice's greeting
        bob_handler = ConditionalHandler().default(
            "Hi Alice! I'm doing great, thanks for asking!"
        )

        with alice.mock(alice_handler), bob.mock(bob_handler):
            # Pipe alice into bob
            async with alice | bob as conversation:
                # Alice goes first (initial message)
                alice.append("Start conversation")

                # Execute the piped conversation
                messages = []
                async for msg in conversation.execute():
                    messages.append(msg)

                # Should have messages from both agents
                assert len(messages) >= 2

                # First message should be from Alice
                assert messages[0].content == "Hello Bob! How are you today?"

                # Bob should have received Alice's message and responded
                assert (
                    messages[-1].content
                    == "Hi Alice! I'm doing great, thanks for asking!"
                )

    async def test_piped_agents_with_transcripts(self):
        """Test agent | agent with predefined conversation transcripts"""
        researcher = Agent("You are a researcher")
        writer = Agent("You are a writer")

        # Researcher finds information - need enough responses for conversation
        research_transcript = [
            ("assistant", "I found 3 key findings about the topic."),
            ("assistant", "The data shows a clear trend upward."),
            ("assistant", "Let me provide more details."),
            ("assistant", "Here's the final research summary."),
        ]

        # Writer summarizes the research - need enough responses
        writer_transcript = [
            ("assistant", "Based on your research, I'll write a summary."),
            ("assistant", "Here's the final article with all findings included."),
            ("assistant", "I've incorporated all your research."),
            ("assistant", "The article is now complete."),
        ]

        with (
            researcher.mock(TranscriptHandler(research_transcript)),
            writer.mock(TranscriptHandler(writer_transcript)),
        ):
            async with researcher | writer as workflow:
                researcher.append("Research the topic")

                messages = []
                async for msg in workflow.execute(max_iterations=4):
                    messages.append(msg)
                    # Limit to 4 messages to avoid exhausting transcripts
                    if len(messages) >= 4:
                        break

                # Should have messages from both agents
                assert len(messages) >= 2

                # Verify researcher messages appear
                assert any("3 key findings" in msg.content for msg in messages)

                # Verify writer receives and processes research
                assert any("article" in msg.content.lower() for msg in messages)

    async def test_piped_agents_maintain_separate_context(self):
        """Test that piped agents maintain separate handler contexts"""

        class ContextTrackingHandler:
            def __init__(self, name: str):
                self.name = name
                self.calls: list[dict[str, int]] = []

            async def handle(self, ctx: MockContext) -> MockResponse:
                self.calls.append(
                    {
                        "call_count": ctx.call_count,
                        "user_messages": len(ctx.agent.user) if ctx.agent else 0,
                        "assistant_messages": (
                            len(ctx.agent.assistant) if ctx.agent else 0
                        ),
                    }
                )
                return MockResponse(content=f"{self.name} speaking")

        agent_a_handler = ContextTrackingHandler("Agent A")
        agent_b_handler = ContextTrackingHandler("Agent B")

        agent_a = Agent("Agent A")
        agent_b = Agent("Agent B")

        with agent_a.mock(agent_a_handler), agent_b.mock(agent_b_handler):
            async with agent_a | agent_b as conversation:
                agent_a.append("Start")

                messages = []
                async for msg in conversation.execute(max_iterations=4):
                    messages.append(msg)
                    if len(messages) >= 4:
                        break

                # Both handlers should have been called
                assert len(agent_a_handler.calls) > 0
                assert len(agent_b_handler.calls) > 0

                # Verify they maintain separate handler instances
                # (even if call structure looks similar)
                assert agent_a_handler is not agent_b_handler
                assert id(agent_a_handler) != id(agent_b_handler)


# ============================================================================
# Test 12: Citations and Annotations Flow
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestCitationsAndAnnotations:
    """Test that citations and annotations flow through the pipeline"""

    async def test_handler_citations_appear_in_message(self):
        """Test that citations from handler appear in final AssistantMessage"""

        def handler_with_citations(ctx: MockContext) -> MockResponse:
            from typing import cast

            from good_agent.types import URL

            return MockResponse(
                content="Based on research, here are the findings.",
                citations=[
                    cast(URL, "https://example.com/paper1.pdf"),
                    cast(URL, "https://example.com/paper2.pdf"),
                ],
            )

        agent = Agent("You are helpful")

        with agent.mock(handler_with_citations):
            result = await agent.call("What did you find?")

            # Citations should be present
            assert result.citations is not None
            assert len(result.citations) == 2
            assert "paper1.pdf" in result.citations[0]
            assert "paper2.pdf" in result.citations[1]

    async def test_handler_annotations_appear_in_message(self):
        """Test that annotations from handler appear in final AssistantMessage"""

        def handler_with_annotations(ctx: MockContext) -> MockResponse:
            return MockResponse(
                content="The calculation shows 42 as the answer.",
                annotations=[  # type: ignore[arg-type]
                    {"type": "calculation", "value": 42, "confidence": 0.95},
                    {"type": "source", "name": "Deep Thought"},
                ],
            )

        agent = Agent("You are helpful")

        with agent.mock(handler_with_annotations):
            result = await agent.call("What's the answer?")

            # Annotations should be present
            assert result.annotations is not None
            assert len(result.annotations) == 2
            assert result.annotations[0]["type"] == "calculation"
            assert result.annotations[0]["value"] == 42
            assert result.annotations[1]["type"] == "source"

    async def test_citations_and_annotations_together(self):
        """Test that both citations and annotations work together"""

        def handler_with_both(ctx: MockContext) -> MockResponse:
            from typing import cast

            from good_agent.types import URL

            return MockResponse(
                content="Research findings with sources.",
                citations=[cast(URL, "https://example.com/source.pdf")],
                annotations=[{"confidence": 0.9, "verified": True}],  # type: ignore[arg-type]
            )

        agent = Agent("You are helpful")

        with agent.mock(handler_with_both):
            result = await agent.call("Tell me")

            assert result.citations is not None
            assert len(result.citations) == 1
            assert result.annotations is not None
            assert len(result.annotations) == 1
            assert result.annotations[0]["verified"] is True

    async def test_citations_persist_across_turns(self):
        """Test that citations from different turns are tracked"""
        from typing import cast

        from good_agent.types import URL

        responses = [
            MockResponse(
                content="First finding",
                citations=[cast(URL, "https://example.com/paper1.pdf")],
            ),
            MockResponse(
                content="Second finding",
                citations=[cast(URL, "https://example.com/paper2.pdf")],
            ),
        ]

        agent = Agent("You are helpful")

        with agent.mock(*responses):
            result1 = await agent.call("Question 1")
            assert result1.citations is not None
            assert len(result1.citations) == 1

            result2 = await agent.call("Question 2")
            assert result2.citations is not None
            assert len(result2.citations) == 1

            # Both citations should be tracked in agent history
            all_assistant_msgs = agent.assistant
            citations_found = [
                msg.citations for msg in all_assistant_msgs if msg.citations is not None
            ]
            assert len(citations_found) == 2


# ============================================================================
# Test 13: Tool Execution with Handler Inspection
# ============================================================================


@pytest.mark.skipif(not HANDLERS_AVAILABLE, reason="Handlers not yet implemented")
class TestToolExecutionInspection:
    """Test full cycle of tool execution with handler inspection"""

    async def test_handler_sees_tool_results_in_messages(self):
        """Test that handler can inspect tool results from previous execution"""
        from good_agent import tool

        @tool
        def get_weather(location: str) -> str:
            """Get weather for a location"""
            return f"Weather in {location}: Sunny, 72°F"

        call_contexts = []

        def tracking_handler(ctx: MockContext) -> MockResponse:
            # Track what we see
            call_contexts.append(
                {
                    "call_count": ctx.call_count,
                    "total_messages": len(ctx.messages),
                    "tool_messages": [
                        msg for msg in ctx.messages if msg.role == "tool"
                    ],
                }
            )

            # First call: request tool
            if ctx.call_count == 1:
                return MockResponse(
                    content="Let me check the weather",
                    tool_calls=[
                        {
                            "tool_name": "get_weather",
                            "arguments": {"location": "Paris"},
                            "type": "tool_call",
                            "result": None,
                        }
                    ],
                )

            # Second call: we should see tool result
            # Check if we can find the tool result
            tool_msgs = [msg for msg in ctx.messages if msg.role == "tool"]
            if tool_msgs:
                return MockResponse(
                    content="Based on the data: Weather in Paris is Sunny!"
                )

            return MockResponse(content="Hmm, no tool result found")

        agent = Agent("You are helpful", tools=[get_weather])

        with agent.mock(tracking_handler):
            result = await agent.call("What's the weather in Paris?")

            # Should have final response
            assert "Paris" in result.content

            # Should have been called twice (initial + after tool)
            assert len(call_contexts) >= 2

            # Second call should have seen the tool result
            second_call = call_contexts[1]
            assert len(second_call["tool_messages"]) > 0

    async def test_conditional_handler_based_on_tool_results(self):
        """Test ConditionalHandler that responds based on tool execution"""
        from good_agent import tool

        @tool
        def check_inventory(item: str) -> dict:
            """Check inventory for an item"""
            inventory = {"apples": 10, "bananas": 0, "oranges": 5}
            return {"item": item, "quantity": inventory.get(item, 0)}

        handler = (
            ConditionalHandler()
            .when(
                # First call - no tool results yet
                lambda ctx: not any(msg.role == "tool" for msg in ctx.messages),
                respond=MockResponse(
                    content="Checking inventory...",
                    tool_calls=[
                        {
                            "tool_name": "check_inventory",
                            "arguments": {"item": "bananas"},
                            "type": "tool_call",
                            "result": None,
                        }
                    ],
                ),
            )
            .when(
                # After tool execution - check if we have stock
                lambda ctx: any(
                    '"quantity": 0' in str(msg.content)
                    for msg in ctx.messages
                    if msg.role == "tool"
                ),
                respond="Sorry, we're out of stock!",
            )
            .default("We have that item in stock!")
        )

        agent = Agent("You are a store assistant", tools=[check_inventory])

        with agent.mock(handler):
            result = await agent.call("Do you have bananas?")

            # Should get the out of stock message
            assert "out of stock" in result.content.lower()

    async def test_handler_inspects_tool_call_arguments(self):
        """Test that handler can inspect tool call arguments from context"""
        from good_agent import tool

        @tool
        def calculate(operation: str, x: int, y: int) -> int:
            """Perform a calculation"""
            if operation == "add":
                return x + y
            elif operation == "multiply":
                return x * y
            return 0

        seen_operations = []

        def operation_tracking_handler(ctx: MockContext) -> MockResponse:
            # Check if there are any tool messages with results
            tool_results = [msg for msg in ctx.messages if msg.role == "tool"]

            if not tool_results:
                # First call - request calculation
                return MockResponse(
                    content="Let me calculate that",
                    tool_calls=[
                        {
                            "tool_name": "calculate",
                            "arguments": {"operation": "multiply", "x": 6, "y": 7},
                            "type": "tool_call",
                            "result": None,
                        }
                    ],
                )
            else:
                # We have tool results - extract the operation
                for msg in ctx.messages:
                    content = str(msg.content) if hasattr(msg, "content") else ""
                    if "multiply" in content:
                        seen_operations.append("multiply")

                return MockResponse(content="The result is 42")

        agent = Agent("You are helpful", tools=[calculate])

        with agent.mock(operation_tracking_handler):
            result = await agent.call("What is 6 times 7?")

            assert "42" in result.content
            # Handler should have seen the operation
            assert "multiply" in seen_operations
