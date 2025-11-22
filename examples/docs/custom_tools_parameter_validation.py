"""Parameter validation using Pydantic Field."""

import asyncio
from typing import Literal

from good_agent import Agent, tool
from pydantic import Field


@tool
async def search(
    query: str = Field(min_length=1, description="Search query"),
    category: Literal["web", "academic", "news"] = Field(default="web"),
    max_results: int = Field(
        default=10, ge=1, le=100, description="Maximum results (1-100)"
    ),
) -> list[dict]:
    """
    Search with validated parameters.

    Args:
        query: The search query (must not be empty)
        category: Category to search
        max_results: Maximum number of results to return

    Returns:
        List of search results
    """
    # Validation happens automatically via Pydantic
    results = []
    for i in range(min(max_results, 5)):
        results.append(
            {
                "title": f"Result {i + 1} for '{query}'",
                "url": f"https://example.com/{i}",
                "category": category,
            }
        )
    return results


async def main():
    """Demonstrate parameter validation with Pydantic Field."""
    async with Agent("Search assistant", tools=[search]) as agent:
        result = await agent.invoke(
            search, query="AI research", category="academic", max_results=5
        )
        print(f"Search results: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
