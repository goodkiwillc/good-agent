"""Multi-turn conversation example."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate multi-turn conversations."""
    async with Agent("You are a helpful assistant.") as agent:
        # First turn
        agent.append("My name is Alice.")
        response1 = await agent.call()
        print(response1.content)  # "Nice to meet you, Alice!"

        # Second turn - agent remembers context
        agent.append("What's my name?")
        response2 = await agent.call()
        print(response2.content)  # "Your name is Alice."


if __name__ == "__main__":
    asyncio.run(main())
