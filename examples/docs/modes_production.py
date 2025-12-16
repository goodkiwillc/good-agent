import asyncio
from datetime import datetime

from good_agent import Agent


async def main():
    async with Agent("Production Agent") as agent:
        # Production mode pattern using v2 API
        @agent.modes("production_ready")
        async def production_ready_mode(agent: Agent):
            """Production-ready mode with comprehensive features."""

            # Initialize mode with safety checks using agent.mode.state
            if not agent.mode.state.get("initialized"):
                # Set up monitoring
                agent.mode.state["start_time"] = datetime.now()
                agent.mode.state["call_count"] = 0
                agent.mode.state["error_count"] = 0
                agent.mode.state["initialized"] = True

            # Update metrics
            agent.mode.state["call_count"] += 1
            agent.mode.state["last_call"] = datetime.now()

            # Add contextual system message via agent.prompt.append()
            call_num = agent.mode.state["call_count"]
            agent.prompt.append(f"Production mode - Call #{call_num}")

            # Automatic cleanup after extended use
            if call_num > 100:
                agent.mode.state.clear()
                agent.mode.state["initialized"] = True

            yield agent

        # Use it
        async with agent.mode("production_ready"):
            await agent.call("Hello prod")


if __name__ == "__main__":
    asyncio.run(main())
