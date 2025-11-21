"""Tool registration examples showing automatic and manual registration."""

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


@tool
def get_current_time() -> str:
    """Get the current time in ISO format."""
    from datetime import datetime

    return datetime.now().isoformat()


async def main():
    """Demonstrate automatic tool registration with agents."""
    # Tools are automatically registered when used with agents
    async with Agent("Assistant", tools=[calculate, get_current_time]) as agent:
        # Tools are automatically registered and available to the LLM
        response = await agent.call("What is 5 + 3?")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
