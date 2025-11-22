"""Maintain state across event invocations."""

import asyncio

from good_agent import Agent, AgentComponent, tool
from good_agent.events import AgentEvents


@tool
def calculate(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


class MetricsComponent(AgentComponent):
    """Component that tracks agent metrics."""

    def __init__(self):
        super().__init__()
        self.message_count = 0
        self.tool_calls = 0
        self.errors = 0

    async def install(self, agent):
        await super().install(agent)

        @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
        def count_message(ctx):
            self.message_count += 1

        @agent.on(AgentEvents.TOOL_CALL_AFTER)
        def count_tool_call(ctx):
            self.tool_calls += 1
            if not ctx.parameters["success"]:
                self.errors += 1

    def get_stats(self) -> dict:
        """Get collected statistics."""
        return {
            "messages": self.message_count,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
            "success_rate": (self.tool_calls - self.errors) / max(1, self.tool_calls),
        }


async def main():
    """Demonstrate stateful event handlers."""
    metrics = MetricsComponent()
    async with Agent("Assistant", tools=[calculate], extensions=[metrics]) as agent:
        await agent.invoke(calculate, a=5, b=3)
        await agent.invoke(calculate, a=10, b=20)
        agent.append("Hello!")

        stats = metrics.get_stats()
        print(f"Session stats: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
