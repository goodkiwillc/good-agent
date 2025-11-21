"""Direct tool invocation for testing or custom workflows."""

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
    """Demonstrate direct tool invocation."""
    async with Agent("Assistant", tools=[calculate]) as agent:
        # Direct tool invocation
        result = await agent.invoke(calculate, operation="add", a=10, b=5)

        print(f"Success: {result.success}")  # True
        print(f"Response: {result.response}")  # 15.0
        print(f"Tool name: {result.tool_name}")  # "calculate"
        print(
            f"Parameters: {result.parameters}"
        )  # {"operation": "add", "a": 10, "b": 5}


if __name__ == "__main__":
    asyncio.run(main())
