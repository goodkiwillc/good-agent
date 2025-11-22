"""Event handler execution order with priorities."""

import asyncio

from good_agent import Agent
from good_agent.events import AgentEvents


async def main():
    """Demonstrate event handler priorities."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.MESSAGE_APPEND_BEFORE, priority=200)
        def high_priority_handler(ctx):
            print("Runs first")

        @agent.on(AgentEvents.MESSAGE_APPEND_BEFORE, priority=100)  # Default priority
        def medium_priority_handler(ctx):
            print("Runs second")

        @agent.on(AgentEvents.MESSAGE_APPEND_BEFORE, priority=50)
        def low_priority_handler(ctx):
            print("Runs last")

        # Trigger message append event
        agent.append("Test message")


if __name__ == "__main__":
    asyncio.run(main())
