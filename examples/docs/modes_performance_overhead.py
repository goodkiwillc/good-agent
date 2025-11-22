import asyncio
from good_agent import Agent, ModeContext

# Mock expensive operations
async def expensive_computation():
    await asyncio.sleep(0.01)
    return "result"

def load_massive_dataset():
    return ["data"] * 1000

async def main():
    async with Agent("Perf Agent") as agent:
        # ❌ Heavy mode handler
        @agent.modes("heavy")
        async def heavy_mode(ctx: ModeContext):
            # Expensive operations in every call
            complex_analysis = await expensive_computation()
            large_data = load_massive_dataset()

            ctx.add_system_message(
                f"Heavy mode with {len(large_data)} items; analysis={complex_analysis}"
            )

        # ✅ Optimized mode handler
        @agent.modes("optimized")
        async def optimized_mode(ctx: ModeContext):
            # Cache expensive operations
            if "analysis_cache" not in ctx.state:
                ctx.state["analysis_cache"] = await expensive_computation()

            # Use cached data
            analysis = ctx.state["analysis_cache"]
            ctx.add_system_message(
                f"Optimized mode using cached analysis: {analysis}"
            )

            # Cleanup state when appropriate
            if ctx.state.get("cleanup_needed"):
                del ctx.state["analysis_cache"]
        
        # Demonstrate usage
        async with agent.modes["optimized"]:
            await agent.call("Test")
            # Second call uses cache
            await agent.call("Test 2")

if __name__ == "__main__":
    asyncio.run(main())
