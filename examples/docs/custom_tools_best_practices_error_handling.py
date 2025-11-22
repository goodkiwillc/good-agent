"""Best practice: Handle errors gracefully."""

import asyncio

from good_agent import Agent, tool


@tool
async def robust_tool(value: str) -> dict:
    """Tool with graceful error handling."""
    try:
        # Process value
        result = int(value)
        return {"success": True, "value": result}
    except ValueError:
        # Return error information instead of raising
        return {
            "success": False,
            "error": "Invalid input: expected a number",
            "input": value,
        }


async def main():
    """Demonstrate graceful error handling best practice."""
    async with Agent("Assistant", tools=[robust_tool]) as agent:
        # Test with valid input
        result = await agent.invoke(robust_tool, value="42")
        print(f"Valid input: {result.response}")

        # Test with invalid input
        result = await agent.invoke(robust_tool, value="not a number")
        print(f"Invalid input: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
