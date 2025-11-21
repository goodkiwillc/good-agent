import asyncio
from datetime import datetime
from good_agent import Agent, ModeContext

async def main():
    agent = Agent("Stateful assistant")

    @agent.modes("session")
    async def session_mode(ctx: ModeContext):
        """Track session information."""
        # Initialize session state
        if "start_time" not in ctx.state:
            ctx.state["start_time"] = datetime.now()
            ctx.state["interaction_count"] = 0
            ctx.state["topics_discussed"] = []

        # Increment interaction counter
        ctx.state["interaction_count"] += 1

        # Add session context to system message
        # ctx.duration might not be available in all versions, using start_time calc
        # Assuming ctx.duration property exists or we calculate it
        duration = datetime.now() - ctx.state["start_time"]
        interactions = ctx.state["interaction_count"]
        ctx.add_system_message(
            f"Session info: {interactions} interactions over {duration}. "
            f"Previous topics: {ctx.state['topics_discussed']}"
        )

    async with agent: # Initialize agent
        async with agent.modes["session"]:
            # First call
            await agent.call("Hello! Let's discuss AI")
            print(f"Interactions: {agent.modes.get_state('interaction_count')}")  # 1

            # Add topic to our tracking
            agent.modes.set_state("topics_discussed", ["AI"])

            # Second call
            await agent.call("What about robotics?")
            print(f"Interactions: {agent.modes.get_state('interaction_count')}")  # 2

            # State persists throughout the mode session
            topics = agent.modes.get_state("topics_discussed")
            topics.append("robotics")
            agent.modes.set_state("topics_discussed", topics)

if __name__ == "__main__":
    asyncio.run(main())
