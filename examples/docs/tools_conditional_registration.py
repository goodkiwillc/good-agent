"""Conditional tool registration based on environment or context."""

import asyncio

from good_agent import Agent, tool


@tool
def production_tool() -> str:
    """Tool only available in production."""
    return "Production data"


@tool
def debug_tool() -> str:
    """Tool only available in debug mode."""
    return "Debug information"


async def main():
    """Demonstrate conditional tool registration."""
    # Conditional registration
    is_production = False  # Example flag
    tools = [production_tool] if is_production else [debug_tool, production_tool]

    async with Agent("Context-aware assistant", tools=tools) as agent:
        response = await agent.call("What tools do you have?")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
