"""Advanced tool invocation options with custom tool call IDs and settings."""

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
    """Demonstrate advanced invocation options."""
    async with Agent("Assistant", tools=[calculate]) as agent:
        # With custom tool call ID
        result = await agent.invoke(
            calculate, tool_call_id="custom_123", operation="multiply", a=6, b=7
        )
        print(f"Custom ID result: {result.response}")

        # Skip creating assistant message (for processing existing tool calls)
        result = await agent.invoke(
            calculate, skip_assistant_message=True, operation="add", a=1, b=2
        )
        print(f"Skip assistant msg result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
