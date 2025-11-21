"""Automatic tool execution by the LLM."""

import asyncio

from good_agent import Agent, tool


@tool
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform basic math operations."""
    if operation == "add":
        return a + b
    elif operation == "multiply":
        return a * b
    else:
        raise ValueError(f"Unknown operation: {operation}")


async def main():
    """Demonstrate automatic tool execution."""
    async with Agent("You are a helpful calculator", tools=[calculate]) as agent:
        # LLM will automatically call the calculate tool
        response = await agent.call("What is 15 * 7?")
        print(response.content)  # "105" or similar


if __name__ == "__main__":
    asyncio.run(main())
