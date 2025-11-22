"""Accessing event context parameters in event handlers."""

import asyncio

from good_agent import Agent, tool
from good_agent.events import AgentEvents


@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main():
    """Demonstrate event context access."""
    async with Agent("Assistant", tools=[calculate]) as agent:

        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def handle_tool_result(ctx):
            # Access event parameters (read-only)
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            response = ctx.parameters.get("response")

            # Access agent that emitted the event
            agent_ref = ctx.parameters["agent"]
            print(f"Agent name: {agent_ref.name}")

            # Check for output from other handlers
            if ctx.output:
                print(f"Previous handler set output: {ctx.output}")

            print(f"Tool {tool_name} {'succeeded' if success else 'failed'}")
            if response and hasattr(response, "response"):
                print(f"Result: {response.response}")

        result = await agent.invoke(calculate, a=5, b=3)
        print(f"\nFinal result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
