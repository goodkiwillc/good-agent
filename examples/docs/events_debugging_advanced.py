"""Advanced event debugging techniques."""

import asyncio

from good_agent import Agent
from good_agent.events import AgentEvents


async def main():
    """Demonstrate advanced event debugging."""
    async with Agent("Assistant") as agent:
        # Check if handlers are registered
        handler_count = len(
            agent.events._handlers.get(AgentEvents.MESSAGE_APPEND_AFTER, [])
        )
        print(f"Handlers for MESSAGE_APPEND_AFTER: {handler_count}")

        # Log all event emissions
        @agent.on("*", priority=1000)  # Highest priority
        def event_logger(ctx):
            print(f"Event emitted: {ctx.event_name}")

        # Trigger some events
        agent.append("First message")
        agent.append("Second message")


if __name__ == "__main__":
    asyncio.run(main())
