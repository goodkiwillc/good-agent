import asyncio
from datetime import datetime
from good_agent import Agent, ModeContext
from good_agent.core.event_router import EventContext

async def main():
    async with Agent("State-monitored agent") as agent:
        @agent.on("mode:state_change")
        def on_state_change(ctx: EventContext):
            mode_name = ctx.parameters.get("mode_name")
            key = ctx.parameters.get("key")
            old_value = ctx.parameters.get("old_value")
            new_value = ctx.parameters.get("new_value")

            print(f"🔄 Mode {mode_name} state change: {key} = {old_value} → {new_value}")

        @agent.modes("stateful")
        async def stateful_mode(ctx: ModeContext):
            """Mode that tracks state changes."""
            ctx.state["counter"] = ctx.state.get("counter", 0) + 1
            ctx.state["last_access"] = datetime.now().isoformat()

            ctx.add_system_message(f"Stateful mode - Call #{ctx.state['counter']}")

        # Usage - state changes will emit events
        async with agent.modes["stateful"]:
            await agent.call("First call")
            await agent.call("Second call")

if __name__ == "__main__":
    asyncio.run(main())
