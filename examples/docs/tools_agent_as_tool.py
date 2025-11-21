"""Converting agents into tools for multi-agent orchestration."""

import asyncio

from good_agent import Agent, tool


@tool
async def web_search(query: str) -> str:
    """Mock web search tool."""
    return f"Search results for: {query}"


async def main():
    """Demonstrate agent as a tool."""
    # 1. Create specialized agents
    researcher = Agent(
        "You are a research specialist. Search for information and summarize findings.",
        name="researcher",
        tools=[web_search],
    )

    # Note: Could also create a writer agent and convert it to a tool
    # writer = Agent("You are a technical writer.", name="writer")
    # writer_tool = writer.as_tool(description="Delegate writing tasks")

    # 2. Convert them to tools
    research_tool = researcher.as_tool(
        description="Delegate research tasks to a specialist agent"
    )

    # 3. Use in a manager agent
    manager = Agent(
        "You are a content manager. Coordinate research and writing.",
        tools=[research_tool],
    )

    async with manager:
        await manager.call("Research the history of AI agents")


if __name__ == "__main__":
    asyncio.run(main())
