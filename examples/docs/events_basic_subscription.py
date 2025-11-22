"""Basic event subscription with @agent.on() decorator."""

import asyncio

from good_agent import Agent
from good_agent.events import AgentEvents


async def main():
    """Demonstrate basic event subscription."""
    async with Agent("Assistant") as agent:

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def on_message_added(ctx):
            message = ctx.parameters["message"]
            print(f"New {message.role} message: {message.content[:50]}...")

        @agent.on(AgentEvents.TOOL_CALL_BEFORE)
        async def on_tool_call(ctx):
            tool_name = ctx.parameters["tool_name"]
            arguments = ctx.parameters["arguments"]
            print(f"Calling tool {tool_name} with {arguments}")

        # Events will fire during normal agent operations
        response = await agent.call("Hello! Can you help me with math?")
        print(f"\nAgent response: {response}")


if __name__ == "__main__":
    asyncio.run(main())
