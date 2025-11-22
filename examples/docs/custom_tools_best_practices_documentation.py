"""Best practice: Provide clear documentation."""

import asyncio

from good_agent import Agent, tool


@tool
async def well_documented_tool(query: str, options: dict | None = None) -> dict:
    """
    Process a query with optional configuration.

    This tool demonstrates comprehensive documentation with:
    - Clear parameter descriptions
    - Expected return value structure
    - Usage examples

    Args:
        query: The search query to process (required)
        options: Optional configuration dictionary:
            - "timeout": Maximum processing time (seconds)
            - "format": Output format preference

    Returns:
        Dictionary containing:
        - "result": Processed output
        - "metadata": Processing information

    Example:
        >>> await well_documented_tool("hello world")
        {"result": "HELLO WORLD", "metadata": {...}}
    """
    return {"result": query.upper(), "metadata": {"options": options or {}}}


async def main():
    """Demonstrate clear documentation best practice."""
    async with Agent("Assistant", tools=[well_documented_tool]) as agent:
        result = await agent.invoke(
            well_documented_tool, query="test", options={"format": "json"}
        )
        print(f"Result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
