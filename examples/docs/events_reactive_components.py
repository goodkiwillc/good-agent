"""Build components that respond to events."""

import asyncio

from good_agent import Agent, AgentComponent
from good_agent.events import AgentEvents


class LoggingComponent(AgentComponent):
    """Component that logs agent operations to a file."""

    def __init__(self, log_file: str = "agent.log"):
        super().__init__()
        self.log_file = log_file

    async def install(self, agent):
        await super().install(agent)

        # Set up event handlers during installation
        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def log_message(ctx):
            message = ctx.parameters["message"]
            with open(self.log_file, "a") as f:
                f.write(f"{message.role}: {message.content}\n")

        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def log_tool_call(ctx):
            tool_name = ctx.parameters["tool_name"]
            success = ctx.parameters["success"]
            with open(self.log_file, "a") as f:
                f.write(f"Tool {tool_name}: {'✅' if success else '❌'}\n")


async def main():
    """Demonstrate reactive component creation."""
    logger = LoggingComponent("session.log")
    async with Agent("Assistant", extensions=[logger]) as agent:
        # All messages and tool calls will be logged
        await agent.call("Hello world!")
        print("Check session.log for logged events")


if __name__ == "__main__":
    asyncio.run(main())
