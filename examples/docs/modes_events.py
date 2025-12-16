import asyncio

from good_agent import Agent
from good_agent.core.event_router import EventContext


async def main():
    async with Agent("Event-monitored agent") as agent:
        # Set up mode event handlers
        @agent.on("mode:enter")
        def on_mode_enter(ctx: EventContext):
            mode_name = ctx.parameters.get("mode_name")
            print(f"Entering mode: {mode_name}")

        @agent.on("mode:exit")
        def on_mode_exit(ctx: EventContext):
            mode_name = ctx.parameters.get("mode_name")
            duration = ctx.parameters.get("duration")
            print(f"Exiting mode: {mode_name} (active for {duration})")

        @agent.on("mode:switch")
        def on_mode_switch(ctx: EventContext):
            old_mode = ctx.parameters.get("old_mode")
            new_mode = ctx.parameters.get("new_mode")
            print(f"Mode switch: {old_mode} -> {new_mode}")

        # Define modes using v2 API (agent: Agent parameter)
        @agent.modes("monitored")
        async def monitored_mode(agent: Agent):
            agent.prompt.append("This mode is being monitored by events.")
            yield agent

        # Use mode - events will fire
        async with agent.mode("monitored"):
            await agent.call("Hello from monitored mode")


if __name__ == "__main__":
    asyncio.run(main())
