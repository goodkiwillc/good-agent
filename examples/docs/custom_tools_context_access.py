"""Accessing agent context from within tools."""

import asyncio

from fast_depends import Depends
from good_agent import Agent, tool
from good_agent.tools import ToolContext


@tool
async def context_aware_tool(
    message: str, context: ToolContext = Depends(ToolContext)
) -> str:
    """
    Tool that accesses agent context.

    Args:
        message: User message
        context: Tool context with agent reference (injected)

    Returns:
        Response incorporating agent state
    """
    agent = context.agent

    # Access agent properties
    message_count = len(agent.messages)

    return f"Processing '{message}' (agent has {message_count} messages)"


async def main():
    """Demonstrate accessing agent context from tools."""
    async with Agent("Assistant", tools=[context_aware_tool]) as agent:
        result = await agent.invoke(context_aware_tool, message="Hello")
        print(result.response)


if __name__ == "__main__":
    asyncio.run(main())
