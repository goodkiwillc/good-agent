"""Tool filtering by name patterns."""

import asyncio

from good_agent import Agent, tool


@tool
async def calculate(operation: str, a: float, b: float) -> float:
    """Perform calculations."""
    return a + b if operation == "add" else a * b


@tool
def get_time() -> str:
    """Get current time."""
    from datetime import datetime

    return datetime.now().isoformat()


@tool
def debug_tool() -> str:
    """Debug information tool."""
    return "Debug data"


@tool
def admin_tool() -> str:
    """Admin operations tool."""
    return "Admin data"


async def main():
    """Demonstrate tool filtering."""
    async with Agent(
        "Restricted assistant",
        tools=[calculate, get_time, debug_tool, admin_tool],
        include_tool_filters=["calculate*", "get_*"],  # Only matching tools
        exclude_tool_filters=["debug*", "admin*"],  # Exclude patterns
    ) as agent:
        # Only 'calculate' and 'get_time' are available
        response = await agent.call("What tools do you have access to?")
        print(response.content)


if __name__ == "__main__":
    asyncio.run(main())
