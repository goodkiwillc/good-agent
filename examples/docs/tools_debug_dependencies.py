"""Debugging dependency injection issues."""

import asyncio

from good_agent import Agent, Depends, tool
from good_agent.tools import ToolContext


@tool
async def debug_tool(param: str, context: ToolContext = Depends()) -> str:
    """Tool for debugging dependencies."""
    print(f"Agent: {context.agent}")
    print(f"Tool call: {context.tool_call}")
    return f"Debug: {param}"


async def main():
    """Demonstrate debugging dependency injection."""
    # Test dependency injection
    async with Agent("Debug agent", tools=[debug_tool]) as agent:
        result = await agent.invoke(debug_tool, param="test")
        print(f"\nResult: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
