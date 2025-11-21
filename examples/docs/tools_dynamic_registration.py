"""Dynamic tool registration during agent execution."""

import asyncio

from good_agent import Agent, tool


@tool
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform calculations."""
    return a + b if operation == "add" else a * b


@tool
async def search_web(query: str) -> str:
    """Search the web."""
    return f"Search results for: {query}"


async def main():
    """Demonstrate dynamic tool registration."""
    async with Agent("Extensible assistant") as agent:
        # Start with basic tools
        await agent.tools.register_tool(calculate, name="math")

        # Add more tools based on conversation
        agent.append("I need to search for something")
        if "search" in agent.user[-1].content.lower():
            await agent.tools.register_tool(search_web, name="web_search")

        response = await agent.call()
        print(response.content)

        # Remove tools
        agent.append("Switch to basic mode")
        if "basic_mode" in agent.user[-1].content:
            del agent.tools["web_search"]


if __name__ == "__main__":
    asyncio.run(main())
