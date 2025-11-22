"""Event handler performance best practices."""

import asyncio
import time

from good_agent import Agent
from good_agent.events import AgentEvents


def heavy_computation():
    """Simulate heavy computation."""
    time.sleep(0.1)
    return "computed"


async def process_message_background(message):
    """Process message in background."""
    await asyncio.sleep(0.1)
    print(f"Background processing complete for: {message.content[:30]}")


async def main():
    """Demonstrate performance best practices."""
    async with Agent("Assistant") as agent:
        # ❌ Heavy computation in handler (blocks entire event system)
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=50)
        def slow_handler(ctx):
            # This will block!
            # heavy_computation()
            pass

        # ✅ Lightweight handler with background processing
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER, priority=100)
        async def fast_handler(ctx):
            # Quick processing
            message = ctx.parameters["message"]

            # Delegate heavy work to background task
            asyncio.create_task(process_message_background(message))

        agent.append("Test message for performance demo")
        await asyncio.sleep(0.2)  # Wait for background tasks


if __name__ == "__main__":
    asyncio.run(main())
