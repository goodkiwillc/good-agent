"""Error handling in agent interactions."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate error handling."""
    async with Agent("Assistant") as agent:
        try:
            response = await agent.call("Hello!")
            print(response.content)
        except Exception as e:
            print(f"Error during agent call: {e}")


if __name__ == "__main__":
    asyncio.run(main())
