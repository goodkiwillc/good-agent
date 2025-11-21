import asyncio
from good_agent import Agent

async def main():
    async with Agent("Assistant") as agent:
        # Monitor agent size
        print(f"Agent has {len(agent)} messages")
        print(f"Version count: {agent._version_manager.version_count}")

        # Clean up if needed
        if len(agent) > 1000:
            # Implement message pruning strategy
            pass

if __name__ == "__main__":
    asyncio.run(main())
