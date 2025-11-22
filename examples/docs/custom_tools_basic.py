"""Basic custom tool definition with parameter validation and error handling."""

import asyncio

from good_agent import Agent, tool


@tool
async def calculate(x: int, y: int, operation: str = "add") -> int:
    """Perform basic arithmetic operations.

    Args:
        x: First number
        y: Second number
        operation: Operation to perform (add, subtract, multiply, divide)

    Returns:
        Result of the operation
    """
    if operation == "add":
        return x + y
    elif operation == "subtract":
        return x - y
    elif operation == "multiply":
        return x * y
    elif operation == "divide":
        if y == 0:
            raise ValueError("Cannot divide by zero")
        return x // y
    else:
        raise ValueError(f"Unknown operation: {operation}")


async def main():
    """Demonstrate basic tool definition."""
    # Use the tool with an agent
    async with Agent("Math assistant", tools=[calculate]) as agent:
        response = await agent.call("What is 15 + 27?")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
