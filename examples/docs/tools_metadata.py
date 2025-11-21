"""Tool metadata customization using decorator parameters."""

import asyncio

from good_agent import Agent, tool


@tool
async def search_documentation(
    query: str,
    limit: int = 5,
) -> list[str]:
    """Search project docs.

    This tool demonstrates metadata customization through the @tool decorator.
    """
    return [f"Result {i}: {query}" for i in range(limit)]


async def main():
    """Demonstrate tool metadata customization."""
    async with Agent(
        "You are a documentation assistant.", tools=[search_documentation]
    ) as agent:
        response = await agent.call("Search for 'async patterns'")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
