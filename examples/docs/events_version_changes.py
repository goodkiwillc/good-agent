"""Track conversation history version changes."""

import asyncio

from good_agent import Agent
from good_agent.core.event_router import EventContext
from good_agent.events import AgentEvents, AgentVersionChangeParams


async def main():
    """Demonstrate version change tracking."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.AGENT_VERSION_CHANGE)
        def on_version_change(ctx: EventContext[AgentVersionChangeParams, None]):
            old_version = ctx.parameters["old_version"]
            new_version = ctx.parameters["new_version"]
            changes = ctx.parameters["changes"]

            print(f"Version {old_version} → {new_version}")
            print(f"Message count: {changes.get('messages', 0)}")

        # Operations that modify conversation history trigger version changes
        agent.append("First message")
        agent.append("Second message")


if __name__ == "__main__":
    asyncio.run(main())
