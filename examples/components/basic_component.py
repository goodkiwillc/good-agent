"""AgentComponent example that registers a tool and listens for events."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.components import AgentComponent
from good_agent.core.event_router import on
from good_agent.events import AgentEvents
from good_agent.mock import MockLanguageModel
from good_agent.tools import tool


class LoggingComponent(AgentComponent):
    """Adds a simple tool and logs each appended message."""

    @tool(description="Uppercase a bit of text")
    async def shout(self, text: str) -> str:
        return text.upper()

    @on(AgentEvents.MESSAGE_APPEND_AFTER)
    def log_append(self, ctx) -> None:
        message = ctx.parameters["message"]
        print(f"component observed {message.role}: {message.content}")


async def main() -> None:
    component = LoggingComponent()
    mock_llm = MockLanguageModel({})
    agent = Agent(
        "You are a cheerful assistant.",
        language_model=mock_llm,
        extensions=[component],
    )

    async with agent:
        await agent.call("say hello")


if __name__ == "__main__":
    asyncio.run(main())
