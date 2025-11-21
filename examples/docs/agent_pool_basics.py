import asyncio
from good_agent import Agent


async def main():
    # Create pool with a list of agents spawned from a template
    base_agent = Agent("Worker")
    # Spawn agents with prompts (ignoring return value as we use a new pool below)
    await base_agent.context_manager.spawn(n=5, prompts=["Worker {{id}}"])

    # AgentPool is just a container, usually created via spawn() or manually
    # We can iterate it or use it as context manager if wrapper supports it,
    # but AgentPool itself isn't an async context manager in the codebase.
    # Let's fix the example to use AgentPool correctly based on source.

    # Correct usage:
    pool = await base_agent.context_manager.spawn(n=5)

    # Get first available agent (simple round robin or just access)
    agent = pool[0]

    try:
        result = await agent.call("Process this task")
        print(f"Agent {agent.id} processed task: {result.content}")
    finally:
        # Return to pool is implicit as pool is just a list wrapper
        pass


if __name__ == "__main__":
    asyncio.run(main())
