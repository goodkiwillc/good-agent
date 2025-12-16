"""Examples: Handler-Based Mocking

This example demonstrates the handler-based mocking API for testing agents
with complex, context-dependent behaviors.

Handler-based mocking allows you to:
- Write context-dependent mock responses
- Test multi-turn workflows
- Test multi-agent conversations
- Create reusable mock patterns
"""

import asyncio

from good_agent import Agent
from good_agent.mock import (
    ConditionalHandler,
    MockContext,
    MockResponse,
    TranscriptHandler,
)

# ============================================================================
# Example 1: Simple Function Handler
# ============================================================================


async def example_function_handler():
    """Most basic handler - a function that returns a MockResponse"""
    print("\n" + "=" * 60)
    print("Example 1: Simple Function Handler")
    print("=" * 60)

    def my_handler(ctx: MockContext) -> MockResponse:
        """Handler is called on each LLM request"""
        return MockResponse(content=f"Response #{ctx.call_count}")

    agent = Agent("You are helpful")

    with agent.mock(my_handler):
        result1 = await agent.call("First question")
        print(f"Call 1: {result1.content}")  # "Response #1"

        result2 = await agent.call("Second question")
        print(f"Call 2: {result2.content}")  # "Response #2"


# ============================================================================
# Example 2: ConditionalHandler - Pattern Matching
# ============================================================================


async def example_conditional_handler():
    """Use ConditionalHandler to respond based on context"""
    print("\n" + "=" * 60)
    print("Example 2: ConditionalHandler - Pattern Matching")
    print("=" * 60)

    handler = (
        ConditionalHandler()
        .when(
            lambda ctx: "weather" in ctx.agent.user[-1].content.lower(),
            respond="It's sunny and 72°F!",
        )
        .when(
            lambda ctx: "time" in ctx.agent.user[-1].content.lower(),
            respond="It's 3:30 PM",
        )
        .when(
            lambda ctx: "name" in ctx.agent.user[-1].content.lower(),
            respond="I'm a helpful AI assistant",
        )
        .default("I don't have that information")
    )

    agent = Agent("You are helpful")

    with agent.mock(handler):
        result = await agent.call("What's the weather like?")
        print(f"Q: Weather → {result.content}")

        result = await agent.call("What time is it?")
        print(f"Q: Time → {result.content}")

        result = await agent.call("What's your name?")
        print(f"Q: Name → {result.content}")

        result = await agent.call("Random question")
        print(f"Q: Random → {result.content}")


# ============================================================================
# Example 3: ConditionalHandler with Complex Logic
# ============================================================================


async def example_conditional_with_state():
    """ConditionalHandler can access full agent state"""
    print("\n" + "=" * 60)
    print("Example 3: ConditionalHandler with State Inspection")
    print("=" * 60)

    handler = (
        ConditionalHandler()
        .when(
            # Check if this is the first call
            lambda ctx: ctx.call_count == 1,
            respond="Welcome! This is your first question.",
        )
        .when(
            # Check if agent has previous assistant messages
            lambda ctx: len(ctx.agent.assistant) > 1,
            respond="I've already answered multiple questions.",
        )
        .default("How can I help?")
    )

    agent = Agent("You are helpful")

    with agent.mock(handler):
        result = await agent.call("Hi")
        print(f"1st call: {result.content}")

        result = await agent.call("Hello again")
        print(f"2nd call: {result.content}")

        result = await agent.call("One more")
        print(f"3rd call: {result.content}")


# ============================================================================
# Example 4: TranscriptHandler - Predefined Conversation
# ============================================================================


async def example_transcript_handler():
    """Use TranscriptHandler to follow a predefined script"""
    print("\n" + "=" * 60)
    print("Example 4: TranscriptHandler - Conversation Script")
    print("=" * 60)

    # Define entire conversation flow upfront
    transcript = [
        ("assistant", "Hello! How can I help you today?"),
        ("assistant", "I can help with that. Let me check..."),
        ("assistant", "Based on my research, here's what I found..."),
        ("assistant", "Is there anything else you'd like to know?"),
    ]

    handler = TranscriptHandler(transcript)
    agent = Agent("You are helpful")

    with agent.mock(handler):
        # Each call returns the next item in the transcript
        for i in range(4):
            result = await agent.call(f"Question {i + 1}")
            print(f"Turn {i + 1}: {result.content}")


# ============================================================================
# Example 5: TranscriptHandler with Tool Calls
# ============================================================================


async def example_transcript_with_tools():
    """TranscriptHandler supports tool calls in the transcript"""
    print("\n" + "=" * 60)
    print("Example 5: TranscriptHandler with Tool Calls")
    print("=" * 60)

    transcript = [
        (
            "assistant",
            "I'll check the weather for you",
            {
                "tool_calls": [
                    {
                        "tool_name": "get_weather",
                        "arguments": {"location": "NYC"},
                        "type": "tool_call",
                        "result": None,
                    }
                ]
            },
        ),
        ("assistant", "The weather in NYC is sunny and 72°F!"),
    ]

    handler = TranscriptHandler(transcript)
    agent = Agent("You are helpful")

    with agent.mock(handler):
        # First response has tool calls
        result1 = await agent.call(
            "What's the weather in NYC?", auto_execute_tools=False
        )
        print(f"Response 1: {result1.content}")
        print(f"  Tool calls: {len(result1.tool_calls) if result1.tool_calls else 0}")

        # Second response is final answer
        result2 = await agent.call("Continue")
        print(f"Response 2: {result2.content}")


# ============================================================================
# Example 6: Multi-Agent Conversations
# ============================================================================


async def example_multi_agent():
    """Each agent can have its own handler"""
    print("\n" + "=" * 60)
    print("Example 6: Multi-Agent with Separate Handlers")
    print("=" * 60)

    # Alice is optimistic
    alice_handler = ConditionalHandler().default("I think we should try it!")

    # Bob is cautious
    bob_handler = ConditionalHandler().default("Let's think this through carefully...")

    alice = Agent("You are Alice, an optimistic agent")
    bob = Agent("You are Bob, a cautious agent")

    with alice.mock(alice_handler), bob.mock(bob_handler):
        alice_response = await alice.call("Should we launch the new feature?")
        print(f"Alice: {alice_response.content}")

        bob_response = await bob.call("Should we launch the new feature?")
        print(f"Bob: {bob_response.content}")


# ============================================================================
# Example 7: Multi-Agent Conversation with TranscriptHandler
# ============================================================================


async def example_multi_agent_conversation():
    """Test agent | agent conversations with coordinated handlers"""
    print("\n" + "=" * 60)
    print("Example 7: Multi-Agent Conversation (agent | agent)")
    print("=" * 60)

    # Create transcripts for each agent
    alice_transcript = [
        ("assistant", "Hi Bob! Want to work on the project together?"),
        ("assistant", "Great! I'll handle the frontend."),
        ("assistant", "Sounds good! Let me know when you're done."),
    ]

    bob_transcript = [
        ("assistant", "Sure Alice! I'd love to collaborate."),
        ("assistant", "Perfect! I'll work on the backend API."),
        ("assistant", "Will do! Looking forward to integrating our work."),
    ]

    alice = Agent("You are Alice")
    bob = Agent("You are Bob")

    with (
        alice.mock(TranscriptHandler(alice_transcript)),
        bob.mock(TranscriptHandler(bob_transcript)),
    ):
        # Start conversation
        async with alice | bob as conversation:
            messages = []
            async for msg in conversation.execute(max_iterations=6):
                speaker = msg.agent.system[0].content if msg.agent.system else "Unknown"
                print(f"{speaker}: {msg.content}")
                messages.append(msg)

                # Stop after 6 messages (3 from each agent)
                if len(messages) >= 6:
                    break


# ============================================================================
# Example 8: Custom Handler Class
# ============================================================================


async def example_custom_handler_class():
    """Create reusable handler classes for complex logic"""
    print("\n" + "=" * 60)
    print("Example 8: Custom Handler Class with State")
    print("=" * 60)

    class StatefulHandler:
        """Handler that maintains state across calls"""

        def __init__(self, personality: str):
            self.personality = personality
            self.questions_asked = 0
            self.topics_discussed: set[str] = set()

        async def handle(self, ctx: MockContext) -> MockResponse:
            self.questions_asked += 1

            # Extract topic from user message (simplified)
            if ctx.agent and ctx.agent.user:
                user_msg = ctx.agent.user[-1].content.lower()
                if "weather" in user_msg:
                    self.topics_discussed.add("weather")
                elif "time" in user_msg:
                    self.topics_discussed.add("time")

            # Generate response based on state
            response = f"[{self.personality}] That's question #{self.questions_asked}. "
            if self.topics_discussed:
                response += f"We've discussed: {', '.join(self.topics_discussed)}"

            return MockResponse(content=response)

    handler = StatefulHandler(personality="Friendly")
    agent = Agent("You are helpful")

    with agent.mock(handler):
        await agent.call("What's the weather?")
        await agent.call("What time is it?")
        result = await agent.call("Tell me something")

        print(f"Final response: {result.content}")
        print(f"Total questions: {handler.questions_asked}")
        print(f"Topics discussed: {handler.topics_discussed}")


# ============================================================================
# Example 9: Debugging with Context Inspection
# ============================================================================


async def example_context_inspection():
    """Use handler to inspect what the agent is doing"""
    print("\n" + "=" * 60)
    print("Example 9: Context Inspection for Debugging")
    print("=" * 60)

    def debug_handler(ctx: MockContext) -> MockResponse:
        """Handler that logs context details"""
        print(f"\n🔍 LLM Call #{ctx.call_count}:")
        if ctx.agent:
            print(f"  - User messages: {len(ctx.agent.user)}")
            print(f"  - Assistant messages: {len(ctx.agent.assistant)}")
        print(f"  - Total messages: {len(ctx.messages)}")

        if ctx.agent and ctx.agent.user:
            last_user_msg = ctx.agent.user[-1].content
            print(f"  - Last user message: {last_user_msg[:50]}...")

        return MockResponse(content="Debug response")

    agent = Agent("You are helpful")

    with agent.mock(debug_handler):
        await agent.call("First question")
        await agent.call("Second question")
        await agent.call("Third question")


# ============================================================================
# Example 10: Backwards Compatibility - Queue-based API
# ============================================================================


async def example_backwards_compatibility():
    """The simple queue-based API still works (uses QueuedResponseHandler internally)"""
    print("\n" + "=" * 60)
    print("Example 10: Queue-Based API (Backwards Compatible)")
    print("=" * 60)

    agent = Agent("You are helpful")

    # Simple string responses - just like before!
    with agent.mock("Response 1", "Response 2", "Response 3"):
        result = await agent.call("Question 1")
        print(f"1: {result.content}")

        result = await agent.call("Question 2")
        print(f"2: {result.content}")

        result = await agent.call("Question 3")
        print(f"3: {result.content}")

    print("\n✅ All old tests still work unchanged!")


# ============================================================================
# Run All Examples
# ============================================================================


async def main():
    """Run all examples"""
    print("\n" + "=" * 70)
    print("HANDLER-BASED MOCKING EXAMPLES")
    print("=" * 70)

    await example_function_handler()
    await example_conditional_handler()
    await example_conditional_with_state()
    await example_transcript_handler()
    await example_transcript_with_tools()
    await example_multi_agent()
    await example_multi_agent_conversation()
    await example_custom_handler_class()
    await example_context_inspection()
    await example_backwards_compatibility()

    print("\n" + "=" * 70)
    print("✨ All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
