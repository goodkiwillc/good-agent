"""Error handling in tools with graceful degradation."""

import asyncio

from good_agent import Agent, tool


@tool
async def divide_numbers(a: float, b: float) -> float:
    """Divide two numbers safely."""
    if b == 0:
        raise ValueError("Division by zero is not allowed")
    return a / b


async def main():
    """Demonstrate tool error handling."""
    # Usage with error handling
    async with Agent("Calculator", tools=[divide_numbers]) as agent:
        result = await agent.invoke(divide_numbers, a=10, b=0)

        if not result.success:
            print(f"Error: {result.error}")
        else:
            print(f"Result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
