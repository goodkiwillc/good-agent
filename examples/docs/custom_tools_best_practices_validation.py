"""Best practice: Use type hints and validation."""

import asyncio

from pydantic import Field

from good_agent import Agent, tool


@tool
async def validated_tool(
    data: str = Field(min_length=1, description="Input data"),
    timeout: int = Field(default=30, ge=1, le=300, description="Timeout in seconds"),
) -> dict:
    """Well-validated tool with clear constraints."""
    # Pydantic handles validation automatically
    return {"data": data, "timeout": timeout}


async def main():
    """Demonstrate type hints and validation best practices."""
    async with Agent("Assistant", tools=[validated_tool]) as agent:
        result = await agent.invoke(validated_tool, data="test input", timeout=60)
        print(f"Validated result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
