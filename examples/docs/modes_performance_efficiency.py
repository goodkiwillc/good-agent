import asyncio
from good_agent import Agent, ModeContext

def load_mode_config():
    return {"setting": "value"}

async def main():
    async with Agent("Efficient Agent") as agent:
        @agent.modes("efficient")
        async def efficient_mode(ctx: ModeContext):
            """Efficient state management patterns."""

            # Use state for caching, not computation
            if "config" not in ctx.state:
                ctx.state["config"] = load_mode_config()  # Load once

            # Store references, not copies
            ctx.state["agent_ref"] = ctx.agent  # Reference, not copy

            # Clean up unused state
            if ctx.state.get("call_count", 0) > 10:
                # Clean up old data after 10 calls
                ctx.state.pop("old_data", None)

            ctx.state["call_count"] = ctx.state.get("call_count", 0) + 1
            
        async with agent.modes["efficient"]:
            await agent.call("Call 1")
            print(f"Call count: {agent.modes.get_state('call_count')}")
            await agent.call("Call 2")
            print(f"Call count: {agent.modes.get_state('call_count')}")

if __name__ == "__main__":
    asyncio.run(main())
