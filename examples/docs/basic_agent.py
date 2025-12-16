import asyncio

from good_agent import Agent


async def main():
    # This example demonstrates the most basic usage of an Agent
    # It uses the default model (gpt-4o-mini) and a simple system prompt
    async with Agent("You are a helpful assistant.") as agent:
        # The call method sends a message to the LLM and returns the response
        response = await agent.call("Say hello!")
        print(f"Agent response: {response.content}")

if __name__ == "__main__":
    asyncio.run(main())
