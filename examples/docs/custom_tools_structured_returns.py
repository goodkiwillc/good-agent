"""Structured return types using Pydantic models."""

import asyncio

from good_agent import Agent, tool
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Individual search result."""

    title: str
    url: str
    snippet: str
    score: float = Field(ge=0.0, le=1.0)


class SearchResponse(BaseModel):
    """Complete search response."""

    query: str
    results: list[SearchResult]
    total_found: int


@tool
async def structured_search(query: str) -> SearchResponse:
    """
    Search with structured response.

    Args:
        query: Search query

    Returns:
        Structured search results with metadata
    """
    results = [
        SearchResult(
            title=f"Result for '{query}'",
            url="https://example.com",
            snippet="Example search result snippet",
            score=0.95,
        )
    ]

    return SearchResponse(query=query, results=results, total_found=len(results))


async def main():
    """Demonstrate structured return types with Pydantic models."""
    async with Agent("Search assistant", tools=[structured_search]) as agent:
        result = await agent.invoke(structured_search, query="Python programming")
        print(f"Structured response: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
