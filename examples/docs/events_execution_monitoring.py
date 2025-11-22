"""Track agent execution cycles and iterations."""

import asyncio

from good_agent import Agent, tool
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, ExecuteIterationParams


@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main():
    """Demonstrate execution iteration monitoring."""
    async with Agent("Assistant", tools=[calculate]) as agent:

        @agent.on(AgentEvents.EXECUTE_BEFORE)
        def on_execute_start(ctx):
            print("🚀 Agent execution started")

        @agent.on(AgentEvents.EXECUTE_ITERATION_BEFORE)
        def before_iteration(ctx: EventContext[ExecuteIterationParams, None]):
            iteration = ctx.parameters.get("iteration", 0)
            print(f"🔄 Starting iteration {iteration}")

        @agent.on(AgentEvents.EXECUTE_ITERATION_AFTER)
        def after_iteration(ctx: EventContext[ExecuteIterationParams, None]):
            iteration = ctx.parameters.get("iteration", 0)
            print(f"✅ Completed iteration {iteration}")

        @agent.on(AgentEvents.EXECUTE_AFTER)
        def on_execute_end(ctx):
            print("🏁 Agent execution completed")

        response = await agent.call("What is 5 + 3?")
        print(f"\nFinal response: {response}")


if __name__ == "__main__":
    asyncio.run(main())
