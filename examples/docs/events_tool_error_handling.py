"""Custom error handling and recovery for tool failures."""

import asyncio

from good_agent import Agent, tool
from good_agent.events import AgentEvents


@tool
async def web_search(query: str) -> list[str]:
    """Search the web (simulated)."""
    # Simulate a timeout error
    raise TimeoutError("Connection timeout")


async def main():
    """Demonstrate tool error handling."""
    async with Agent("Assistant", tools=[web_search]) as agent:

        @agent.on(AgentEvents.TOOL_CALL_ERROR)
        async def handle_tool_error(ctx):
            tool_name = ctx.parameters["tool_name"]
            error = ctx.parameters["error"]

            # Log detailed error information
            print(f"Tool {tool_name} failed: {error}")

            # Implement retry logic for specific tools
            if tool_name == "web_search" and "timeout" in str(error).lower():
                print("Retrying web search with longer timeout...")
                # Could trigger a retry by emitting another tool call event

        try:
            result = await agent.invoke(web_search, query="python")
            print(f"Result: {result.response}")
        except Exception as e:
            print(f"Tool invocation failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
