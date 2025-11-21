"""Agent-as-tool with multi-turn conversation support."""

import asyncio

from good_agent import Agent


async def main():
    """Demonstrate multi-turn sessions with agent tools."""
    researcher = Agent("You are a research specialist.", name="researcher", tools=[])

    # Disable multi-turn for stateless, one-shot execution
    stateless_tool = researcher.as_tool(multi_turn=False)

    # Enable multi-turn (default) for stateful sessions
    stateful_tool = researcher.as_tool(multi_turn=True)

    # With multi_turn=True:
    # - First call creates a session with ID
    # - Subsequent calls continue the same conversation
    # - State persists for parent agent's lifecycle

    async with Agent("Manager", tools=[stateful_tool, stateless_tool]) as manager:
        await manager.call("Start a research session")


if __name__ == "__main__":
    asyncio.run(main())
