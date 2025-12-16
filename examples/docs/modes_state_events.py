import asyncio
from datetime import datetime

from good_agent import Agent
from good_agent.core.event_router import EventContext


async def main():
    async with Agent("State-monitored agent") as agent:

        @agent.on("mode:state_change")
        def on_state_change(ctx: EventContext):
            mode_name = ctx.parameters.get("mode_name")
            key = ctx.parameters.get("key")
            old_value = ctx.parameters.get("old_value")
            new_value = ctx.parameters.get("new_value")

            print(f"Mode {mode_name} state change: {key} = {old_value} -> {new_value}")

        @agent.modes("stateful")
        async def stateful_mode(agent: Agent):
            """Mode that tracks state changes."""
            agent.mode.state["counter"] = agent.mode.state.get("counter", 0) + 1
            agent.mode.state["last_access"] = datetime.now().isoformat()

            agent.prompt.append(f"Stateful mode - Call #{agent.mode.state['counter']}")
            yield agent

        # Usage - state changes will emit events
        async with agent.mode("stateful"):
            await agent.call("First call")
            await agent.call("Second call")


if __name__ == "__main__":
    asyncio.run(main())
