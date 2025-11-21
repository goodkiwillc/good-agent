"""Basic tool definition examples showing how to create tools with the @tool decorator."""

import asyncio
from datetime import datetime

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


@tool
def get_current_time() -> str:
    """Get the current time in ISO format."""
    return datetime.now().isoformat()


async def main():
    """Example demonstrating basic tool definitions."""
    # Tools can be async or sync, with type hints and docstrings
    async with Agent(
        "You are a helpful assistant.", tools=[calculate, get_current_time]
    ) as agent:
        response = await agent.call("What is 5 + 3 and what time is it?")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
