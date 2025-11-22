"""Stop event propagation or cancel operations."""

import asyncio

from good_agent import Agent, tool
from good_agent.core.event_router import ApplyInterrupt
from good_agent.events import AgentEvents


@tool
def delete_file(filename: str) -> str:
    """Delete a file (dangerous operation)."""
    return f"Deleted {filename}"


@tool
def safe_operation(value: int) -> int:
    """A safe operation."""
    return value * 2


async def main():
    """Demonstrate interrupting event flows for security."""
    async with Agent("Assistant", tools=[delete_file, safe_operation]) as agent:

        @agent.on(AgentEvents.TOOL_CALL_BEFORE, priority=200)
        def security_check(ctx):
            tool_name = ctx.parameters["tool_name"]

            # Block dangerous tools
            if tool_name in ["delete_file", "system_command"]:
                print(f"⛔ Blocked dangerous tool: {tool_name}")
                raise ApplyInterrupt("Security policy violation")

        # This will be blocked
        try:
            result = await agent.invoke(delete_file, filename="important.txt")
            print(f"Delete result: {result.response}")
        except ApplyInterrupt as e:
            print(f"Tool call prevented: {e}")

        # This will succeed
        result = await agent.invoke(safe_operation, value=10)
        print(f"Safe operation result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
