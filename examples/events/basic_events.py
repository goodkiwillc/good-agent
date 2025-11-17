"""Attach AgentEvents handlers and inspect EventContext data."""

from __future__ import annotations

import asyncio

from good_agent.agent import Agent
from good_agent.events import AgentEvents

try:  # pragma: no cover
    from .._shared.mock_llm import ExampleLanguageModel, assistant_response
except ImportError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from _shared.mock_llm import ExampleLanguageModel, assistant_response  # type: ignore[no-redef]


async def main() -> None:
    agent = Agent(
        language_model=ExampleLanguageModel([assistant_response("Hello events!")]),
    )
    agent.append("Log every assistant reply.", role="system")

    @agent.on(AgentEvents.MESSAGE_APPEND_AFTER)
    def record_message(ctx):
        message = ctx.parameters["message"]
        print(f"event: appended {message.role}: {message.content}")

    async with agent:
        await agent.call("say hello")


if __name__ == "__main__":
    asyncio.run(main())
