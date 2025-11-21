"""Tool context dependencies - accessing agent state within tools."""

import asyncio

from fast_depends import Depends

from good_agent import Agent, tool
from good_agent.tools import ToolContext


@tool
async def agent_aware_tool(
    query: str,
    context: ToolContext = Depends(ToolContext),  # Injected agent context
) -> str:
    """Tool that can access agent state."""
    agent = context.agent

    # Access agent properties
    agent_name = agent.name
    message_count = len(agent.messages)

    return f"Agent {agent_name} ({message_count} messages): {query}"


async def main():
    """Demonstrate tool context access."""
    async with Agent("Context-aware assistant", tools=[agent_aware_tool]) as agent:
        response = await agent.call("Tell me about yourself")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
