"""Message history access patterns."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate message history access."""
    async with Agent("You are a helpful assistant.") as agent:
        agent.append("My name is Alice.")
        await agent.call()

        # Get messages by index
        print(f"System message: {agent[0].content[:50]}...")  # System prompt
        print(f"First user message: {agent[1].content}")  # First user message
        print(f"Last message: {agent[-1].content[:50]}...")  # Most recent message

        # Get messages by role
        print(f"User messages: {len(agent.user)}")  # All user messages
        print(f"Assistant messages: {len(agent.assistant)}")  # All assistant messages

        # Iterate over all messages
        for message in agent.messages:
            print(f"{message.role}: {message.content}")


if __name__ == "__main__":
    asyncio.run(main())
