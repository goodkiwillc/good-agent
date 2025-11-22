"""Enable event debugging to see all events."""

import asyncio
import logging

from good_agent import Agent

# Enable event debugging
logging.getLogger("good_agent.events").setLevel(logging.DEBUG)


async def main():
    """Demonstrate event debugging."""
    async with Agent("Assistant") as agent:
        # Add debug handler to see all events
        @agent.on("*")  # Listen to all events
        def debug_all_events(ctx):
            event_name = ctx.event_name
            params = list(ctx.parameters.keys())
            print(f"Event: {event_name} with params: {params}")

        # Trigger some events
        agent.append("Test message")
        agent.append("Another message", role="assistant")


if __name__ == "__main__":
    asyncio.run(main())
