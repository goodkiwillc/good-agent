import asyncio

from good_agent import Agent


# Mock expensive operations
async def expensive_computation():
    await asyncio.sleep(0.01)
    return "result"


def load_massive_dataset():
    return ["data"] * 1000


async def main():
    async with Agent("Perf Agent") as agent:
        # Heavy mode handler (not recommended)
        @agent.modes("heavy")
        async def heavy_mode(agent: Agent):
            # Expensive operations in every call
            complex_analysis = await expensive_computation()
            large_data = load_massive_dataset()

            agent.prompt.append(
                f"Heavy mode with {len(large_data)} items; analysis={complex_analysis}"
            )
            yield agent

        # Optimized mode handler (recommended)
        @agent.modes("optimized")
        async def optimized_mode(agent: Agent):
            # Cache expensive operations in agent.mode.state
            if "analysis_cache" not in agent.mode.state:
                agent.mode.state["analysis_cache"] = await expensive_computation()

            # Use cached data
            analysis = agent.mode.state["analysis_cache"]
            agent.prompt.append(f"Optimized mode using cached analysis: {analysis}")

            # Cleanup state when appropriate
            if agent.mode.state.get("cleanup_needed"):
                del agent.mode.state["analysis_cache"]
            yield agent

        # Demonstrate usage
        async with agent.modes["optimized"]:
            await agent.call("Test")
            # Second call uses cache
            await agent.call("Test 2")


if __name__ == "__main__":
    asyncio.run(main())
