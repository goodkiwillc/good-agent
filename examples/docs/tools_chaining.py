"""Tool chaining - tools calling other tools."""

import asyncio

from fast_depends import Depends

from good_agent import Agent, tool
from good_agent.tools import ToolContext


@tool
async def search_and_summarize(
    query: str,
    context: ToolContext = Depends(ToolContext),
) -> str:
    """Search for information and summarize results."""
    agent = context.agent

    # Call search tool (mock implementation)
    search_result = await agent.invoke("search_web", query=query)

    if search_result.success:
        # Process results and call summarization (mock)
        summary_result = await agent.invoke(
            "summarize_text", text=search_result.response
        )
        return (
            summary_result.response if summary_result.success else "Failed to summarize"
        )

    return "Search failed"


@tool
async def search_web(query: str) -> str:
    """Mock web search."""
    return f"Search results for: {query}"


@tool
async def summarize_text(text: str) -> str:
    """Mock text summarization."""
    return f"Summary of: {text[:50]}..."


async def main():
    """Demonstrate tool chaining."""
    async with Agent(
        "Research assistant", tools=[search_and_summarize, search_web, summarize_text]
    ) as agent:
        response = await agent.call("Search and summarize Python async patterns")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
