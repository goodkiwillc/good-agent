"""Mock events for testing components."""

import asyncio

import pytest

from good_agent import Agent, AgentComponent
from good_agent.events import AgentEvents
from good_agent.messages import UserMessage


class LoggingComponent(AgentComponent):
    """Component that logs messages to a file."""

    def __init__(self, log_file: str = "test.log"):
        super().__init__()
        self.log_file = log_file

    async def install(self, agent):
        await super().install(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def log_message(ctx):
            message = ctx.parameters["message"]
            with open(self.log_file, "a") as f:
                f.write(f"{message.role}: {message.content}\n")


@pytest.mark.asyncio
async def test_component_event_handling():
    """Test component handles events correctly."""
    component = LoggingComponent("test.log")
    agent = Agent("Test")
    await component.install(agent)

    # Emit test event
    await agent.events.apply(
        AgentEvents.MESSAGE_APPEND_AFTER, message=UserMessage("Test"), agent=agent
    )

    # Verify logging occurred
    with open("test.log") as f:
        content = f.read()
        assert "user: Test" in content


async def main():
    """Run the test."""
    await test_component_event_handling()
    print("Component test passed!")


if __name__ == "__main__":
    asyncio.run(main())
