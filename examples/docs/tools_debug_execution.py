"""Debugging tool execution errors."""

import asyncio

from good_agent import Agent, tool


@tool
async def risky_tool(param: str) -> str:
    """Tool that may fail."""
    if param == "fail":
        raise ValueError("Intentional failure for demonstration")
    return f"Success: {param}"


async def main():
    """Demonstrate handling tool execution errors."""
    # Handle tool execution errors
    async with Agent("Error-handling agent", tools=[risky_tool]) as agent:
        # Test successful execution
        result = await agent.invoke(risky_tool, param="test")
        print(f"Success case: {result.response}\n")

        # Test error case
        result = await agent.invoke(risky_tool, param="fail")

        if not result.success:
            print(f"Tool failed: {result.error}")
            print(f"Parameters used: {result.parameters}")
            if result.traceback:
                print(f"Traceback available: {len(result.traceback)} characters")


if __name__ == "__main__":
    asyncio.run(main())
