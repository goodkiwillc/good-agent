import asyncio

from good_agent import Agent


def load_mode_config():
    return {"setting": "value"}


async def main():
    async with Agent("Efficient Agent") as agent:

        @agent.modes("efficient")
        async def efficient_mode(agent: Agent):
            """Efficient state management patterns using v2 API."""

            # Use agent.mode.state for caching, not computation
            if "config" not in agent.mode.state:
                agent.mode.state["config"] = load_mode_config()  # Load once

            # Clean up unused state
            if agent.mode.state.get("call_count", 0) > 10:
                # Clean up old data after 10 calls
                agent.mode.state.pop("old_data", None)

            agent.mode.state["call_count"] = agent.mode.state.get("call_count", 0) + 1
            yield agent

        async with agent.mode("efficient"):
            await agent.call("Call 1")
            print(f"Call count: {agent.modes.get_state('call_count')}")
            await agent.call("Call 2")
            print(f"Call count: {agent.modes.get_state('call_count')}")


if __name__ == "__main__":
    asyncio.run(main())
