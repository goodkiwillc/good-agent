"""AgentComponent example that registers a tool and listens for events."""

from __future__ import annotations

import asyncio

from good_agent import Agent, AgentComponent, tool
from good_agent.core.event_router import on
from good_agent.events import AgentEvents


try:  # pragma: no cover - support running via ``python``
    from .._shared.mock_llm import ExampleLanguageModel, assistant_response
except ImportError:  # pragma: no cover
    import sys
    from pathlib import Path

    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from _shared.mock_llm import (  # type: ignore[no-redef]
        ExampleLanguageModel,
        assistant_response,
    )


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
    agent = Agent(
        language_model=ExampleLanguageModel(
            [assistant_response("Hello from component!")]
        ),
        extensions=[component],
    )
    agent.append("You are a cheerful assistant.", role="system")

    async with agent:
        await agent.call("say hello")


if __name__ == "__main__":
    asyncio.run(main())
