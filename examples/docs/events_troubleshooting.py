"""Common event handling issues and solutions."""

import asyncio

from good_agent import Agent, tool
from good_agent.events import AgentEvents


@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


async def main():
    """Demonstrate common event handling issues and fixes."""
    async with Agent("Assistant", tools=[calculate]) as agent:
        # ❌ Handler not called - wrong event name
        # @agent.on("typo:event:name")  # Wrong event name
        # def bad_handler(ctx): pass

        # ✅ Use correct event names from AgentEvents
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def good_event_name_handler(ctx):
            print("✅ Handler with correct event name called")

        # ❌ Handler exceptions breaking event chain
        @agent.on(AgentEvents.TOOL_CALL_AFTER, priority=50)
        def bad_error_handler(ctx):
            # This would break other handlers!
            # raise ValueError("Oops")
            pass

        # ✅ Handle exceptions gracefully
        @agent.on(AgentEvents.TOOL_CALL_AFTER, priority=100)
        def good_error_handler(ctx):
            try:
                # Handler logic
                tool_name = ctx.parameters["tool_name"]
                print(f"✅ Tool {tool_name} completed")
            except Exception as e:
                print(f"Handler error: {e}")
                # Don't re-raise unless intentionally interrupting

        # Trigger events
        agent.append("Test message")
        await agent.invoke(calculate, a=5, b=3)


if __name__ == "__main__":
    asyncio.run(main())
