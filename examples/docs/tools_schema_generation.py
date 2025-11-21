"""Automatic schema generation from type hints."""

import asyncio
from typing import Literal

from pydantic import Field

from good_agent import Agent, tool


@tool
async def advanced_search(
    query: str,
    limit: int = Field(default=10, ge=1, le=100, description="Number of results"),
    sort_by: Literal["relevance", "date", "title"] = "relevance",
    include_content: bool = True,
    categories: list[str] | None = None,
) -> dict:
    """Advanced search with validation and schema generation."""
    return {
        "query": query,
        "results": [f"Result {i}" for i in range(min(limit, 5))],
        "sort_by": sort_by,
        "categories": categories or [],
    }


async def main():
    """Demonstrate automatic schema generation."""
    # Schema is automatically available to LLM
    async with Agent("Search assistant", tools=[advanced_search]) as agent:
        # LLM understands parameter constraints and types
        await agent.call("Search for 'python' with at most 5 results sorted by date")


if __name__ == "__main__":
    asyncio.run(main())
