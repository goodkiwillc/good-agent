"""Track and modify tool executions."""

import asyncio

from good_agent import Agent, tool
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, ToolCallAfterParams, ToolCallBeforeParams


@tool
async def search(query: str, limit: int = 5) -> list[str]:
    """Search for items."""
    return [f"Result {i + 1} for '{query}'" for i in range(limit)]


async def main():
    """Demonstrate tool call monitoring."""
    async with Agent("Assistant", tools=[search]) as agent:

        @agent.on(AgentEvents.TOOL_CALL_BEFORE)
        async def before_tool_call(ctx: EventContext[ToolCallBeforeParams, dict]):
            tool_name = ctx.parameters["tool_name"]
            arguments = ctx.parameters["arguments"]

            # Log tool calls
            print(f"🛠️  Calling {tool_name} with {arguments}")

            # Modify arguments if needed
            if tool_name == "search" and "limit" not in arguments:
                modified_args = arguments.copy()
                modified_args["limit"] = 10
                ctx.output = modified_args  # Return modified arguments
                return modified_args

        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def after_tool_call(ctx: EventContext[ToolCallAfterParams, None]):
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            response = ctx.parameters.get("response")

            if success:
                print(f"✅ {tool_name} succeeded")
                if response and hasattr(response, "response"):
                    result = response.response
                    print(f"   Result: {str(result)[:100]}...")
            else:
                error = ctx.parameters.get("error", "Unknown error")
                print(f"❌ {tool_name} failed: {error}")

        result = await agent.invoke(search, query="python")
        print(f"\nSearch results: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
