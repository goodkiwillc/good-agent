"""Trigger additional events based on conditions."""

import asyncio

from good_agent import Agent, tool
from good_agent.events import AgentEvents


@tool
async def search(query: str) -> list[str]:
    """Search for items."""
    return [f"Result {i + 1} for '{query}'" for i in range(3)]


async def main():
    """Demonstrate event chaining with custom events."""
    async with Agent("Assistant", tools=[search]) as agent:

        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        async def chain_events(ctx):
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]

            if tool_name == "search" and success:
                # Emit custom event for successful searches
                await agent.events.apply(
                    "search:success", result=ctx.parameters["response"]
                )

        # Handle custom event
        @agent.on("search:success")
        def on_successful_search(ctx):
            result = ctx.parameters["result"]
            print(f"Search succeeded with {len(result.response)} results")

        result = await agent.invoke(search, query="python")
        print(f"\nSearch results: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
