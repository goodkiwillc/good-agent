"""Monitor agent initialization and state transitions."""

import asyncio

from good_agent import Agent, tool
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, AgentInitializeParams, AgentStateChangeParams


@tool
def sample_tool(value: int) -> int:
    """Sample tool for demo."""
    return value * 2


async def main():
    """Demonstrate agent lifecycle events."""
    async with Agent("Assistant", tools=[sample_tool]) as agent:

        @agent.on(AgentEvents.AGENT_INIT_AFTER)
        def on_agent_ready(ctx: EventContext[AgentInitializeParams, None]):
            agent_ref = ctx.parameters["agent"]
            tools = ctx.parameters["tools"]
            print(f"Agent {agent_ref.name} initialized with {len(tools)} tools")

        @agent.on(AgentEvents.AGENT_STATE_CHANGE)
        def on_state_change(ctx: EventContext[AgentStateChangeParams, None]):
            old_state = ctx.parameters["old_state"]
            new_state = ctx.parameters["new_state"]
            print(f"Agent state: {old_state} → {new_state}")

        # Agent operations will trigger state changes
        result = await agent.invoke(sample_tool, value=10)
        print(f"Result: {result.response}")


if __name__ == "__main__":
    asyncio.run(main())
