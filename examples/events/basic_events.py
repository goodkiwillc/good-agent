"""Attach AgentEvents handlers and inspect EventContext data."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.events import AgentEvents
from good_agent.mock import MockLanguageModel


async def main() -> None:
    agent = Agent(
        "Log every assistant reply.",
        language_model=MockLanguageModel({}),
    )

    @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
    def record_message(ctx):
        message = ctx.parameters["message"]
        print(f"event: appended {message.role}: {message.content}")

    async with agent:
        await agent.call("say hello")


if __name__ == "__main__":
    asyncio.run(main())
