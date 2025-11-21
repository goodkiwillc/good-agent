import asyncio
from good_agent import Agent


async def main():
    async with Agent("Base agent") as agent:
        agent.append("Shared context")

        # Fork for parallel processing
        async with agent.fork_context() as fork1, agent.fork_context() as fork2:
            # Each fork has independent message history
            task1 = asyncio.create_task(fork1.call("Process option A"))
            task2 = asyncio.create_task(fork2.call("Process option B"))

            results = await asyncio.gather(task1, task2)
            print(f"Results: {[r.content for r in results]}")

        # Original agent unchanged by fork operations
        # Count includes: 1 SystemMessage + 1 UserMessage ("Shared context")
        assert len(agent) == 2
        # Note: System prompt + User message = 2 messages
        # Let's verify specific content
        print(f"Original agent messages: {[m.content for m in agent.messages]}")


if __name__ == "__main__":
    asyncio.run(main())
