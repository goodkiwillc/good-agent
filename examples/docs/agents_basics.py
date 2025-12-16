import asyncio

from good_agent import Agent


async def main():
    # Basic initialization
    async with Agent("You are a helpful assistant.") as agent:
        response = await agent.call("Hello!")
        print(response.content)

    # Manual initialization (not recommended for most use cases)
    agent = Agent("System prompt")
    await agent.initialize()  # Must call before using

    try:
        response = await agent.call("Hello!")
    finally:
        await agent.close()  # Cleanup resources

if __name__ == "__main__":
    asyncio.run(main())
