import asyncio
from datetime import datetime

from good_agent import Agent


async def main():
    agent = Agent("Stateful assistant")

    @agent.modes("session")
    async def session_mode(agent: Agent):
        """Track session information."""
        # Initialize session state via agent.mode.state
        if "start_time" not in agent.mode.state:
            agent.mode.state["start_time"] = datetime.now()
            agent.mode.state["interaction_count"] = 0
            agent.mode.state["topics_discussed"] = []

        # Increment interaction counter
        agent.mode.state["interaction_count"] += 1

        # Add session context to system message
        duration = datetime.now() - agent.mode.state["start_time"]
        interactions = agent.mode.state["interaction_count"]
        agent.prompt.append(
            f"Session info: {interactions} interactions over {duration}. "
            f"Previous topics: {agent.mode.state['topics_discussed']}"
        )

    async with agent:  # Initialize agent
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
